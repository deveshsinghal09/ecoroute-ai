"""SageMaker supplies train/serve. The same image can be configured with Lambda RIC."""

import json
import os
import runpy
import sys


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "train"
    if command == "train":
        sys.argv = [
            "train.py",
            "--prepared-dir",
            "/opt/ml/input/data/dataset",
            "--output",
            "/opt/ml/model",
        ]
        runpy.run_path("/app/scripts/train.py", run_name="__main__")
    elif command == "serve":
        import uvicorn
        from fastapi import FastAPI, HTTPException, Request
        from ecoroute.ml.inference import LocalRegistry
        from ecoroute.ml.training import matrix

        registry = LocalRegistry(os.getenv("SM_MODEL_DIR", "/opt/ml/model"))
        manifest = registry.select()
        model = registry.load(manifest)
        app = FastAPI(docs_url=None, redoc_url=None)

        @app.get("/ping")
        def ping():
            return {"status": "ready"}

        @app.post("/invocations")
        async def invoke(request: Request):
            body = await request.body()
            if len(body) > 1024 * 1024:
                raise HTTPException(413)
            rows = json.loads(body)
            if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
                raise HTTPException(422)
            from ecoroute.ml.preprocessing import FEATURES

            if any(set(r) != set(FEATURES) for r in rows):
                raise HTTPException(422)
            return {
                "model_version": manifest["model_version"],
                "horizon_hours": 1,
                "predictions_ug_m3": model.predict(matrix(rows)).clip(min=0).tolist(),
            }

        uvicorn.run(app, host="0.0.0.0", port=8080, access_log=False)
    else:
        raise ValueError("Only SageMaker train/serve commands are supported")


if __name__ == "__main__":
    main()
