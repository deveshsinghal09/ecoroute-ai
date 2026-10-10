"""Publish existing frontend build only with explicit apply/cost consent and verified IAM identity."""
import argparse
import json
import sys
import zipfile
from pathlib import Path

import boto3
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.manage_cloud import guard_identity  # noqa: E402


def upload_zip(bundle, upload_url, transport=None):
    """Failure text must never expose the temporary signed upload credential."""
    try:
        with bundle.open("rb") as stream, httpx.Client(timeout=120, trust_env=False, transport=transport) as http:
            response = http.put(upload_url, content=stream, headers={"content-type": "application/zip"})
            if not 200 <= response.status_code < 300:
                raise SystemExit("frontend_upload_failed; temporary URL redacted")
    except httpx.HTTPError:
        raise SystemExit("frontend_upload_failed; temporary URL redacted") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=["cloudfront", "amplify"], required=True)
    parser.add_argument("--outputs", default="work/deployed-outputs.json")
    parser.add_argument("--profile")
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--expected-account-id")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--accept-estimated-charges", action="store_true")
    args = parser.parse_args(argv)
    build = ROOT / "frontend/dist"
    print(json.dumps({"target": args.target, "apply": args.apply, "build_exists": (build / "index.html").exists(),
        "missing_names": [name for name, value in (("AWS_PROFILE", args.profile), ("EXPECTED_AWS_ACCOUNT_ID", args.expected_account_id)) if not value],
        "prerequisites": ["real API/Cognito VITE configuration baked into build", "exact CORS and PKCE callback", "hosting outputs", "publish IAM"],
        "charges": "S3/upload, hosting/transfer and invalidation usage; review before --apply"}, indent=2))
    if not args.apply:
        return 0
    if not args.profile or not args.expected_account_id or not args.accept_estimated_charges:
        parser.error("Configure profile/account, review cost and obtain publication approval before apply")
    if not (build / "index.html").exists():
        parser.error("Build frontend with real public API/Cognito configuration first")
    outputs = json.loads(Path(args.outputs).read_text())["EcoRouteHosting"]
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    guard_identity(session.client("sts").get_caller_identity(), args.expected_account_id)
    if args.target == "cloudfront":
        import mimetypes
        client = session.client("s3")
        for file in build.rglob("*"):
            if file.is_file():
                key = file.relative_to(build).as_posix()
                client.upload_file(str(file), outputs["FrontendBucket"], key, ExtraArgs={
                    "ContentType": mimetypes.guess_type(file.name)[0] or "application/octet-stream",
                    "CacheControl": "public,max-age=31536000,immutable" if key.startswith("assets/") else "no-cache",
                    "ServerSideEncryption": "AES256"})
        from uuid import uuid4
        result = session.client("cloudfront").create_invalidation(DistributionId=outputs["DistributionId"],
            InvalidationBatch={"Paths": {"Quantity": 1, "Items": ["/*"]}, "CallerReference": str(uuid4())})
        print(json.dumps({"status": "uploaded_invalidation_submitted", "invalidation_status": result["Invalidation"]["Status"]}))
    else:
        (ROOT / "work").mkdir(exist_ok=True)
        bundle = ROOT / "work/frontend.zip"
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in build.rglob("*"):
                if file.is_file():
                    archive.write(file, file.relative_to(build).as_posix())
        if bundle.stat().st_size > 500000000:
            parser.error("Demo upload limit 500 MB exceeded")
        client = session.client("amplify")
        upload = client.create_deployment(appId=outputs["AmplifyAppId"], branchName="main")
        # Upload URL is a temporary credential; never print/log it.
        upload_zip(bundle, upload["zipUploadUrl"])
        result = client.start_deployment(appId=outputs["AmplifyAppId"], branchName="main", jobId=upload["jobId"])
        print(json.dumps({"status": "deployment_submitted", "job_status": result["jobSummary"]["status"]}))
    print("Verify hosted page and authenticated API in browser; submitted is not verified deployment success.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
