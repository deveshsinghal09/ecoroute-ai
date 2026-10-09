"""Consistent owner-scoped storage with atomic consent checks and event deduplication."""
import hashlib
import json
import time
import uuid

from botocore.exceptions import ClientError
from fastapi import HTTPException

from ecoroute.storage import Conflict, LocalStore, Unavailable, fingerprint


def owner_key(subject):
    return hashlib.sha256(subject.encode()).hexdigest()


def topic(subject, device):
    return f"ecoroute/users/{owner_key(subject)}/devices/{device}/measurements"


def item(pk, sk, payload, expires, **extra):
    return {"pk": {"S": pk}, "sk": {"S": sk}, "payload": {"S": json.dumps(payload)},
            "expires_at": {"N": str(expires)}, **extra}


class WearableRepository:
    def __init__(self, store, table=""):
        self.store, self.table = store, table
        self.local = isinstance(store, LocalStore)
        if not self.local and not table:
            raise Unavailable("wearables_table_not_configured")

    def get(self, pk, sk):
        if self.local:
            return self.store.get("wearable", pk, sk)
        row = self.store.client.get_item(TableName=self.table,
            Key={"pk": {"S": pk}, "sk": {"S": sk}}, ConsistentRead=True).get("Item")
        if not row or int(row["expires_at"]["N"]) <= time.time():
            return None
        return json.loads(row["payload"]["S"])

    def device(self, subject, device):
        result = self.get(owner_key(subject), "device#" + device)
        if not result or result["owner_sub"] != subject:
            raise HTTPException(404, "device_not_found")
        return result

    def register(self, subject, body, key):
        pk, now = owner_key(subject), int(time.time())
        sk = "registration#" + fingerprint(key)
        data = body.model_dump(mode="json")
        prior = self.get(pk, sk)
        if prior:
            if prior["fingerprint"] != fingerprint(data):
                raise Conflict()
            return self.device(subject, prior["device_id"]), False
        device = uuid.uuid4().hex
        record = {**data, "device_id": device, "owner_sub": subject, "owner_key": pk,
            "consent": {"telemetry": False, "location": False, "history": False, "correlation": False},
            "epoch": 0, "deleting": False, "certificate_thumbprint": None,
            "created_at": now, "expires_at": now + 90 * 86400}
        registration = {"fingerprint": fingerprint(data), "device_id": device}
        if self.local:
            with self.store.lock, self.store.db:
                # Recheck under lock; requests cannot create duplicate devices.
                prior = self.get(pk, sk)
                if prior:
                    if prior["fingerprint"] != fingerprint(data):
                        raise Conflict()
                    return self.device(subject, prior["device_id"]), False
                self.store.put_record("wearable", pk, "device#" + device, record, 90 * 86400)
                self.store.put_record("wearable", pk, sk, registration, 90 * 86400)
        else:
            try:
                self.store.client.transact_write_items(TransactItems=[
                    {"Put": {"TableName": self.table, "Item": self.device_item(record)}},
                    {"Put": {"TableName": self.table, "Item": item(pk, sk, registration, record["expires_at"]),
                             "ConditionExpression": "attribute_not_exists(pk) OR expires_at <= :now",
                             "ExpressionAttributeValues": {":now": {"N": str(now)}}}},
                ])
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "TransactionCanceledException":
                    raise
                prior = self.get(pk, sk)
                if not prior or prior["fingerprint"] != fingerprint(data):
                    raise Conflict() from None
                return self.device(subject, prior["device_id"]), False
        return record, True

    @staticmethod
    def device_item(record):
        return item(record["owner_key"], "device#" + record["device_id"], record, record["expires_at"],
            epoch={"N": str(record["epoch"])}, consent={"BOOL": record["consent"]["telemetry"]},
            deleting={"BOOL": record["deleting"]})

    def consent(self, subject, body, *, deleting=False):
        pk = owner_key(subject)
        if self.local:
            with self.store.lock, self.store.db:
                old = self.device(subject, body.device_id)
                if old["deleting"] and not deleting:
                    raise HTTPException(409, "device_deleted_register_new_device")
                record = {**old, "consent": body.model_dump(exclude={"device_id"}),
                          "epoch": old["epoch"] + 1, "deleting": deleting,
                          "consent_updated_at": int(time.time()), "expires_at": int(time.time()) + 90 * 86400}
                self.store.put_record("wearable", pk, "device#" + body.device_id, record, 90 * 86400)
                return record
        old = self.device(subject, body.device_id)
        if old["deleting"] and not deleting:
            raise HTTPException(409, "device_deleted_register_new_device")
        record = {**old, "consent": body.model_dump(exclude={"device_id"}),
                  "epoch": old["epoch"] + 1, "deleting": deleting,
                  "consent_updated_at": int(time.time()), "expires_at": int(time.time()) + 90 * 86400}
        try:
            self.store.client.put_item(TableName=self.table, Item=self.device_item(record),
                ConditionExpression="epoch = :old", ExpressionAttributeValues={":old": {"N": str(old["epoch"])}})
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            raise HTTPException(409, "consent_changed_retry") from None
        return record

    def ingest(self, subject, body, *, allow_demo=False):
        data, pk, now = body.model_dump(mode="json"), owner_key(subject), int(time.time())
        if body.user_id != subject:
            raise HTTPException(403, "telemetry_identity_mismatch")
        if (body.provenance.synthetic or body.provenance.bridge == "demo") and not allow_demo:
            raise HTTPException(403, "synthetic_telemetry_disabled")
        stamp = int(body.timestamp.timestamp() * 1000)
        sk = f"measurement#{body.device_id}#{stamp:013d}#{body.event_id}"
        event_sk = f"event#{body.device_id}#{body.event_id}"
        digest = fingerprint(data)

        def prepare():
            device = self.device(subject, body.device_id)
            if device["deleting"] or not device["consent"]["telemetry"]:
                raise HTTPException(403, "wearable_consent_required")
            if body.provenance.bridge != device["bridge"]:
                raise HTTPException(422, "bridge_provenance_mismatch")
            if body.position and not device["consent"]["location"]:
                raise HTTPException(403, "location_consent_required")
            record = {**data, "consent_epoch": device["epoch"], "archive": device["consent"].get("history", False),
                      "received_at": now, "expires_at": stamp // 1000 + 7 * 86400}
            return device, record

        def replay(record):
            prior = self.get(pk, event_sk)
            if prior:
                if prior["fingerprint"] != digest:
                    raise Conflict()
                saved = self.get(pk, prior["measurement_key"])
                if not saved or saved["consent_epoch"] != record["consent_epoch"]:
                    raise Conflict()
                return saved, False
            return None

        if self.local:
            with self.store.lock, self.store.db:
                device, record = prepare()
                repeated = replay(record)
                if repeated:
                    return repeated
                expires = record["expires_at"]
                self.store.put_record("wearable", pk, sk, record, max(1, expires - now))
                self.store.put_record("wearable", pk, event_sk,
                    {"fingerprint": digest, "measurement_key": sk}, max(1, expires - now))
                return record, True
        device, record = prepare()
        repeated = replay(record)
        if repeated:
            return repeated
        try:
            self.store.client.transact_write_items(TransactItems=[
                {"ConditionCheck": {"TableName": self.table,
                    "Key": {"pk": {"S": pk}, "sk": {"S": "device#" + body.device_id}},
                    "ConditionExpression": "epoch = :epoch AND consent = :yes AND deleting = :no AND expires_at > :now",
                    "ExpressionAttributeValues": {":epoch": {"N": str(device["epoch"])},
                        ":yes": {"BOOL": True}, ":no": {"BOOL": False}, ":now": {"N": str(now)}}}},
                {"Put": {"TableName": self.table, "Item": item(pk, sk, record, record["expires_at"])}},
                {"Put": {"TableName": self.table, "Item": item(pk, event_sk,
                    {"fingerprint": digest, "measurement_key": sk}, record["expires_at"]),
                    "ConditionExpression": "attribute_not_exists(pk)"}},
            ])
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "TransactionCanceledException":
                raise
            _, fresh = prepare()
            repeated = replay(fresh)
            if repeated:
                return repeated
            raise HTTPException(409, "consent_changed_retry") from None
        return record, True

    def history(self, subject, device, start, end, *, limit=200, cursor=None):
        pk, prefix = owner_key(subject), f"measurement#{device}#"
        low = prefix + f"{int(start.timestamp() * 1000):013d}#"
        high = prefix + f"{int(end.timestamp() * 1000):013d}#" + "f" * 32
        if cursor and not low <= cursor <= high:
            raise HTTPException(422, "invalid_cursor")
        if self.local:
            with self.store.lock:
                rows = self.store.db.execute(
                    "SELECT id,payload FROM records WHERE kind='wearable' AND owner=? AND id BETWEEN ? AND ? AND expires>? AND id>? ORDER BY id LIMIT ?",
                    (pk, low, high, int(time.time()), cursor or "", limit + 1)).fetchall()
            return [json.loads(r[1]) for r in rows[:limit]], rows[limit - 1][0] if len(rows) > limit else None
        request = {"TableName": self.table, "KeyConditionExpression": "pk = :pk AND sk BETWEEN :low AND :high",
            "ExpressionAttributeValues": {":pk": {"S": pk}, ":low": {"S": low}, ":high": {"S": high}},
            "ConsistentRead": True, "Limit": limit}
        if cursor:
            request["ExclusiveStartKey"] = {"pk": {"S": pk}, "sk": {"S": cursor}}
        response = self.store.client.query(**request)
        return [json.loads(r["payload"]["S"]) for r in response.get("Items", [])
                if int(r["expires_at"]["N"]) > time.time()], response.get("LastEvaluatedKey", {}).get("sk", {}).get("S")

    def purge(self, subject, device):
        pk, prefixes = owner_key(subject), (f"measurement#{device}#", f"event#{device}#")
        if self.local:
            with self.store.lock, self.store.db:
                for prefix in prefixes:
                    self.store.db.execute("DELETE FROM records WHERE kind='wearable' AND owner=? AND id LIKE ?", (pk, prefix + "%"))
            return False
        pending = False
        for prefix in prefixes:
            response = self.store.client.query(TableName=self.table,
                KeyConditionExpression="pk = :pk AND begins_with(sk, :prefix)",
                ExpressionAttributeValues={":pk": {"S": pk}, ":prefix": {"S": prefix}},
                ProjectionExpression="pk, sk", ConsistentRead=True, Limit=200)
            for row in response.get("Items", []):
                self.store.client.delete_item(TableName=self.table, Key=row)
            pending = pending or bool(response.get("LastEvaluatedKey"))
        return pending
