"""Render hardened Kubernetes resources from real CDK outputs; does not contact a cluster."""
import argparse
import json
from pathlib import Path


def manifest(outputs):
    image = outputs["BackendImage"]
    environment = json.loads(outputs["BackendEnvironment"])
    if "@sha256:" not in image or environment.get("ECOROUTE_PROFILE") != "aws":
        raise ValueError("Expected deployed image digest and AWS backend configuration")
    namespace = {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "ecoroute"}}
    service_account = {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "backend", "namespace": "ecoroute"}}
    pod = {"serviceAccountName": "backend", "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "fsGroup": 10001},
        "containers": [{"name": "backend", "image": image, "ports": [{"containerPort": 8000}],
            "env": [{"name": k, "value": v} for k, v in environment.items()],
            "resources": {"requests": {"cpu": "250m", "memory": "256Mi"}, "limits": {"cpu": "500m", "memory": "512Mi"}},
            "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]}},
            "livenessProbe": {"httpGet": {"path": "/api/v1/health", "port": 8000}, "initialDelaySeconds": 20},
            "readinessProbe": {"httpGet": {"path": "/api/v1/health", "port": 8000}, "initialDelaySeconds": 10},
            "volumeMounts": [{"name": "scratch", "mountPath": "/tmp"}]}], "volumes": [{"name": "scratch", "emptyDir": {"sizeLimit": "64Mi"}}]}
    deployment = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "backend", "namespace": "ecoroute"},
        "spec": {"replicas": 1, "selector": {"matchLabels": {"app": "ecoroute-backend"}},
            "template": {"metadata": {"labels": {"app": "ecoroute-backend"}}, "spec": pod}}}
    service = {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "backend", "namespace": "ecoroute"},
        "spec": {"type": "ClusterIP", "selector": {"app": "ecoroute-backend"}, "ports": [{"port": 8000, "targetPort": 8000}]}}
    return {"apiVersion": "v1", "kind": "List", "items": [namespace, service_account, deployment, service]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", default="work/deployed-outputs.json")
    parser.add_argument("--out", default="work/eks-backend.json")
    args = parser.parse_args(argv)
    result = manifest(json.loads(Path(args.outputs).read_text())["EcoRouteCompute"])
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Rendered backend resources. No kubectl action performed; apply only to approved EKS cluster.")


if __name__ == "__main__":
    main()
