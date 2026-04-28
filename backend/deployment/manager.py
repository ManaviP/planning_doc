"""Kubernetes deployment management for selected workload scenarios."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
from kubernetes.client.rest import ApiException
import yaml

from backend.db import insert_log
from backend.models import DeploymentScenario, WorkloadRequest

WORKLOAD_NAMESPACE = "workloads"
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 120


class DeploymentError(RuntimeError):
    """Raised when Kubernetes deployment operations fail."""


class DeploymentManager:
    def __init__(self) -> None:
        self._load_cluster_config()
        if getattr(self, "_mock_mode", False):
            self.apps_v1 = None
            self.core_v1 = None
        else:
            self.apps_v1 = client.AppsV1Api()
            self.core_v1 = client.CoreV1Api()

    @staticmethod
    def _is_running_in_docker() -> bool:
        return Path("/.dockerenv").exists() or os.getenv("RUNNING_IN_DOCKER", "").lower() == "true"

    @staticmethod
    def _rewrite_host_local_server(url: str) -> str:
        return url.replace("127.0.0.1", "host.docker.internal").replace("localhost", "host.docker.internal")

    @staticmethod
    def _map_windows_kube_path(path_value: str) -> str:
        normalized = path_value.replace("\\", "/")
        lower = normalized.lower()
        if "/.minikube/" in lower:
            suffix = normalized[lower.index("/.minikube/") + len("/.minikube/") :]
            return f"/root/.minikube/{suffix.lstrip('/')}"
        if "/.kube/" in lower:
            suffix = normalized[lower.index("/.kube/") + len("/.kube/") :]
            return f"/root/.kube/{suffix.lstrip('/')}"
        return path_value

    def _load_cluster_config(self) -> None:
        try:
            config.load_incluster_config()
            return
        except ConfigException:
            pass

        kubeconfig_path = os.getenv("KUBECONFIG", str(Path.home() / ".kube" / "config"))
        kube_path = Path(kubeconfig_path)
        if not kube_path.exists():
            self._mock_mode = True
            return

        with kube_path.open("r", encoding="utf-8") as fh:
            kubeconfig_dict = yaml.safe_load(fh) or {}

        if self._is_running_in_docker():
            for cluster in kubeconfig_dict.get("clusters", []):
                cluster_meta = cluster.get("cluster", {})
                server = cluster_meta.get("server")
                if isinstance(server, str):
                    cluster_meta["server"] = self._rewrite_host_local_server(server)
                    cluster_meta["insecure-skip-tls-verify"] = True
                    cluster_meta.pop("certificate-authority", None)
                    cluster_meta.pop("certificate-authority-data", None)

                cert_auth = cluster_meta.get("certificate-authority")
                if isinstance(cert_auth, str):
                    cluster_meta["certificate-authority"] = self._map_windows_kube_path(cert_auth)

            for user in kubeconfig_dict.get("users", []):
                user_meta = user.get("user", {})
                for field in ("client-certificate", "client-key"):
                    value = user_meta.get(field)
                    if isinstance(value, str):
                        user_meta[field] = self._map_windows_kube_path(value)

        try:
            config.load_kube_config_from_dict(kubeconfig_dict)
            self._mock_mode = False
        except Exception as exc:  # pragma: no cover - external environment dependent
            self._mock_mode = True

    def _ensure_namespace(self) -> None:
        if getattr(self, "_mock_mode", False):
            return
        try:
            self.core_v1.read_namespace(WORKLOAD_NAMESPACE)
        except ApiException as exc:
            if exc.status != 404:
                raise
            namespace = client.V1Namespace(metadata=client.V1ObjectMeta(name=WORKLOAD_NAMESPACE))
            self.core_v1.create_namespace(namespace)

    def _build_manifest(self, workload: WorkloadRequest, scenario: DeploymentScenario) -> dict[str, Any]:
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": workload.workload_id,
                "namespace": WORKLOAD_NAMESPACE,
                "labels": {"app": workload.workload_id},
            },
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app": workload.workload_id}},
                "template": {
                    "metadata": {"labels": {"app": workload.workload_id}},
                    "spec": {
                        "nodeSelector": {"kubernetes.io/hostname": scenario.target_node},
                        "restartPolicy": "Always",
                        "containers": [
                            {
                                "name": workload.workload_id,
                                "image": workload.container_image,
                                "imagePullPolicy": "IfNotPresent",
                                "resources": {
                                    "requests": {
                                        "cpu": str(workload.cpu_cores),
                                        "memory": f"{int(workload.memory_gb * 1024)}Mi",
                                    }
                                },
                            }
                        ],
                    },
                },
            },
        }

    def _list_workload_pods(self, workload_id: str) -> list[client.V1Pod]:
        if getattr(self, "_mock_mode", False):
            return []
        response = self.core_v1.list_namespaced_pod(
            namespace=WORKLOAD_NAMESPACE,
            label_selector=f"app={workload_id}",
        )
        return response.items

    def create_deployment(self, workload: WorkloadRequest, scenario: DeploymentScenario) -> None:
        if getattr(self, "_mock_mode", False):
            insert_log(workload.workload_id, f"Mock Mode: Simulating deployment to {scenario.target_node}...", "info")
            return

        try:
            self._ensure_namespace()
            manifest = self._build_manifest(workload, scenario)
            self.apps_v1.create_namespaced_deployment(namespace=WORKLOAD_NAMESPACE, body=manifest)
        except ApiException as exc:
            insert_log(workload.workload_id, f"Deployment API error: {exc}", "error")
            raise DeploymentError(f"Failed to create deployment for {workload.workload_id}: {exc}") from exc

    def deploy(self, workload: WorkloadRequest, scenario: DeploymentScenario) -> dict[str, str]:
        self.create_deployment(workload, scenario)

        deadline = time.time() + POLL_TIMEOUT_SECONDS
        last_status = {"phase": "Pending", "pod_name": "", "node": scenario.target_node}

        while time.time() < deadline:
            try:
                pods = self._list_workload_pods(workload.workload_id)
            except ApiException as exc:
                insert_log(workload.workload_id, f"Failed to query pod status: {exc}", "error")
                raise DeploymentError(f"Failed to query pod status for {workload.workload_id}: {exc}") from exc

            if pods:
                pod = pods[0]
                pod_name = pod.metadata.name if pod.metadata else "unknown-pod"
                phase = pod.status.phase if pod.status and pod.status.phase else "Unknown"
                node_name = pod.spec.node_name if pod.spec and pod.spec.node_name else scenario.target_node
                insert_log(workload.workload_id, f"Pod {pod_name}: {phase}", "info")
                last_status = {"phase": phase, "pod_name": pod_name, "node": node_name}
                if phase in {"Running", "Succeeded", "Failed"}:
                    return last_status

            time.sleep(POLL_INTERVAL_SECONDS)

        insert_log(workload.workload_id, "Deployment polling timed out.", "error")
        return {"phase": "Failed", "pod_name": last_status["pod_name"], "node": last_status["node"]}

    def get_pod_status(self, workload_id: str) -> dict[str, str]:
        if getattr(self, "_mock_mode", False):
            return {"phase": "Running", "pod_name": f"{workload_id}-mock", "node": "mock-node"}

        try:
            pods = self._list_workload_pods(workload_id)
        except ApiException as exc:
            insert_log(workload_id, f"Failed to read pod status: {exc}", "error")
            raise DeploymentError(f"Failed to read pod status for {workload_id}: {exc}") from exc

        if not pods:
            return {"phase": "NotFound", "pod_name": "", "node": ""}

        pod = pods[0]
        return {
            "phase": pod.status.phase if pod.status and pod.status.phase else "Unknown",
            "pod_name": pod.metadata.name if pod.metadata else "unknown-pod",
            "node": pod.spec.node_name if pod.spec and pod.spec.node_name else "",
        }

    def delete_deployment(self, workload_id: str) -> bool:
        if getattr(self, "_mock_mode", False):
            return True

        try:
            self.apps_v1.delete_namespaced_deployment(
                name=workload_id,
                namespace=WORKLOAD_NAMESPACE,
                body=client.V1DeleteOptions(propagation_policy="Foreground"),
            )
            return True
        except ApiException as exc:
            if exc.status == 404:
                return False
            insert_log(workload_id, f"Failed to delete deployment: {exc}", "error")
            raise DeploymentError(f"Failed to delete deployment for {workload_id}: {exc}") from exc
