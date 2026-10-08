"""Owner-scoped JSON records. Atomic create + idempotency prevents duplicate requests."""
import hashlib
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from botocore.exceptions import ClientError


class Conflict(Exception):
    pass


class Unavailable(Exception):
    pass


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def operation_id(owner, kind, key):
    return fingerprint([owner, kind, key])


class LocalStore:
    """SQLite is an offline adapter, not a DynamoDB emulator."""
    def __init__(self, path):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS records (
              owner TEXT, kind TEXT, id TEXT, payload TEXT, expires INTEGER,
              PRIMARY KEY(owner, kind, id));
            CREATE TABLE IF NOT EXISTS operations (
              id TEXT PRIMARY KEY, fingerprint TEXT, record_id TEXT, expires INTEGER);
        """)

    def ready(self):
        with self.lock:
            self.db.execute("SELECT 1")
        return True

    def create(self, kind, owner, data, key, ttl=604800):
        now = int(time.time())
        operation = operation_id(owner, kind, key)
        digest = fingerprint(data)
        with self.lock, self.db:
            self.db.execute("DELETE FROM records WHERE expires <= ?", (now,))
            self.db.execute("DELETE FROM operations WHERE expires <= ?", (now,))
            prior = self.db.execute("SELECT fingerprint,record_id FROM operations WHERE id=?",
                                    (operation,)).fetchone()
            if prior:
                if prior[0] != digest:
                    raise Conflict()
                record = self.get(kind, owner, prior[1])
                if record is None:
                    raise Conflict()
                return record, False
            record = {"id": uuid.uuid4().hex, "created_at": now, "expires_at": now + ttl, **data}
            self.db.execute("INSERT INTO records VALUES(?,?,?,?,?)",
                            (owner, kind, record["id"], json.dumps(record), now + ttl))
            self.db.execute("INSERT INTO operations VALUES(?,?,?,?)",
                            (operation, digest, record["id"], now + min(ttl, 86400)))
            return record, True

    def get(self, kind, owner, identifier):
        with self.lock:
            row = self.db.execute(
                "SELECT payload FROM records WHERE owner=? AND kind=? AND id=? AND expires>?",
                (owner, kind, identifier, int(time.time())),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put_record(self, kind, owner, identifier, data, ttl):
        record = {**data, "id": identifier, "expires_at": int(time.time()) + ttl}
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?,?,?)",
                            (owner, kind, identifier, json.dumps(record), record["expires_at"]))
        return record

    def put_preferences(self, owner, data):
        expires = int(time.time()) + 90 * 86400
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?,?,?)",
                            (owner, "preferences", "settings", json.dumps(data), expires))
        return data


class DynamoStore:
    def __init__(self, client, tables, idempotency_table):
        self.client, self.tables, self.idempotency_table = client, tables, idempotency_table

    def ready(self):
        for table in set(self.tables.values()) | {self.idempotency_table}:
            if self.client.describe_table(TableName=table)["Table"]["TableStatus"] != "ACTIVE":
                return False
        return True

    def get(self, kind, owner, identifier):
        response = self.client.get_item(
            TableName=self.tables[kind], Key={"pk": {"S": owner}, "sk": {"S": kind + "#" + identifier}},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item or int(item["expires_at"]["N"]) <= time.time():
            return None
        return json.loads(item["payload"]["S"])

    def create(self, kind, owner, data, key, ttl=604800):
        now = int(time.time())
        digest = fingerprint(data)
        op = operation_id(owner, kind, key)
        op_key = {"pk": {"S": owner}, "sk": {"S": op}}
        record = {"id": uuid.uuid4().hex, "created_at": now, "expires_at": now + ttl, **data}
        item = {"pk": {"S": owner}, "sk": {"S": kind + "#" + record["id"]},
                "payload": {"S": json.dumps(record)}, "expires_at": {"N": str(now + ttl)}}
        try:
            self.client.transact_write_items(TransactItems=[
                {"Put": {"TableName": self.idempotency_table,
                         "Item": {**op_key, "fingerprint": {"S": digest},
                                  "record_id": {"S": record["id"]},
                                  "expires_at": {"N": str(now + min(ttl, 86400))}},
                         "ConditionExpression": "attribute_not_exists(pk) OR expires_at <= :now",
                         "ExpressionAttributeValues": {":now": {"N": str(now)}}}},
                {"Put": {"TableName": self.tables[kind], "Item": item,
                         "ConditionExpression": "attribute_not_exists(pk)"}},
            ])
            return record, True
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "TransactionCanceledException":
                raise
            previous = self.client.get_item(TableName=self.idempotency_table, Key=op_key,
                                            ConsistentRead=True).get("Item")
            if not previous or int(previous["expires_at"]["N"]) <= now:
                raise Unavailable() from exc
            if previous["fingerprint"]["S"] != digest:
                raise Conflict() from exc
            prior = self.get(kind, owner, previous["record_id"]["S"])
            if prior is None:
                raise Conflict() from exc
            return prior, False

    def put_record(self, kind, owner, identifier, data, ttl):
        record = {**data, "id": identifier, "expires_at": int(time.time()) + ttl}
        self.client.put_item(TableName=self.tables[kind], Item={
            "pk": {"S": owner}, "sk": {"S": kind + "#" + identifier},
            "payload": {"S": json.dumps(record)}, "expires_at": {"N": str(record["expires_at"])}})
        return record

    def put_preferences(self, owner, data):
        self.client.put_item(TableName=self.tables["preferences"], Item={
            "pk": {"S": owner}, "sk": {"S": "preferences#settings"},
            "payload": {"S": json.dumps(data)},
            "expires_at": {"N": str(int(time.time()) + 90 * 86400)},
        })
        return data
