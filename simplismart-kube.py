#!/usr/bin/env python3
import argparse
import subprocess
import yaml
import json
import os
from typing import Dict, Any, Optional

class KubernetesAutomation:
    def __init__(self, kubeconfig: str = None, namespace: str = "default"):
        self.kubeconfig = kubeconfig
        self.namespace = namespace
        self.helm_installed = False
        self.keda_installed = False
        self.helm_path = self.find_helm_path()

    def run_command(self, command: str, check: bool = True) -> subprocess.CompletedProcess:
        try:
            if os.name == 'nt':  # Windows
                command = f'powershell -Command "{command}"'
            
            result = subprocess.run(
                command,
                shell=True,
                check=check,
                text=True,
                capture_output=True
            )
            return result
        except subprocess.CalledProcessError as e:
            print(f"Error executing command: {e.cmd}")
            print(f"Error output: {e.stderr}")
            raise

    def find_helm_path(self) -> str:
        try:
            result = self.run_command("where helm", check=False)
            if result.returncode == 0:
                return "helm"
            
            possible_paths = [
                r"C:\Program Files\helm.exe",
                r"C:\ProgramData\chocolatey\bin\helm.exe",
                r"C:\Program Files\Helm\bin\helm.exe"
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    return f'"{path}"'
            
            return "helm" 
        except Exception as e:
            print(f"Warning: Could not determine Helm path: {str(e)}")
            return "helm"

    def connect_to_cluster(self) -> bool:
        """Verify connection to Kubernetes cluster."""
        try:
            cmd = "kubectl cluster-info"
            if self.kubeconfig:
                cmd += f" --kubeconfig={self.kubeconfig}"
            result = self.run_command(cmd)
            print("Successfully connected to Kubernetes cluster")
            print(result.stdout)
            return True
        except Exception as e:
            print(f"Failed to connect to cluster: {str(e)}")
            return False

    def install_helm(self) -> bool:
        try:
            result = self.run_command(f"{self.helm_path} version", check=False)
            if result.returncode == 0:
                print("Helm is already installed")
                self.helm_installed = True
                return True

            print("Installing Helm...")
            try:
                self.run_command("choco install kubernetes-helm -y")
            except:
                self.run_command("winget install helm.helm")
            
            self.helm_path = self.find_helm_path()
            
            self.run_command(f"{self.helm_path} version")
            self.helm_installed = True
            print("Helm installed successfully")
            return True
        except Exception as e:
            print(f"Failed to install Helm: {str(e)}")
            return False

    def install_keda(self) -> bool:
        if not self.helm_installed:
            print("Helm is required to install KEDA")
            return False

        try:
            print("Adding KEDA Helm repository...")
            self.run_command(f"{self.helm_path} repo add kedacore https://kedacore.github.io/charts")
            self.run_command(f"{self.helm_path} repo update")

            print("Installing KEDA...")
            cmd = f'{self.helm_path} install keda kedacore/keda --namespace keda --create-namespace'
            if self.kubeconfig:
                cmd += f' --kubeconfig="{self.kubeconfig}"'
            self.run_command(cmd)

            print("Verifying KEDA installation...")
            cmd = 'kubectl get pods -n keda'
            if self.kubeconfig:
                cmd += f' --kubeconfig="{self.kubeconfig}"'
            result = self.run_command(cmd)
            
            if "keda-operator" in result.stdout:
                self.keda_installed = True
                print("KEDA installed successfully")
                return True
            else:
                print("KEDA installation verification failed")
                return False
        except Exception as e:
            print(f"Failed to install KEDA: {str(e)}")
            return False

    def verify_keda_installation(self) -> bool:
        try:
            print("\nVerifying KEDA installation...")
            
            print("\nChecking KEDA pods:")
            cmd = "kubectl get pods -n keda"
            if self.kubeconfig:
                cmd += f" --kubeconfig={self.kubeconfig}"
            result = self.run_command(cmd)
            print(result.stdout)
            
            if "keda-operator" not in result.stdout or "Running" not in result.stdout:
                print("KEDA operator pod not running")
                return False
            
            print("\nChecking KEDA deployments:")
            cmd = "kubectl get deployments -n keda"
            if self.kubeconfig:
                cmd += f" --kubeconfig={self.kubeconfig}"
            result = self.run_command(cmd)
            print(result.stdout)
            
            if "keda-operator" not in result.stdout or "1/1" not in result.stdout:
                print("KEDA operator deployment not ready")
                return False
            
            print("\nChecking KEDA CRDs:")
            cmd = "kubectl get crd"
            if self.kubeconfig:
                cmd += f" --kubeconfig={self.kubeconfig}"
            result = self.run_command(cmd)
            
            required_crds = ["scaledobjects.keda.sh", "triggerauthentications.keda.sh"]
            missing_crds = [crd for crd in required_crds if crd not in result.stdout]
            
            if missing_crds:
                print(f"Missing required CRDs: {', '.join(missing_crds)}")
                return False
            
            print("\n KEDA is properly installed and running")
            return True
            
        except Exception as e:
            print(f"Verification failed: {str(e)}")
            return False

    def create_deployment(
        self,
        name: str,
        image: str,
        tag: str = "latest",
        replicas: int = 1,
        cpu_request: str = "100m",
        cpu_limit: str = "500m",
        memory_request: str = "128Mi",
        memory_limit: str = "512Mi",
        ports: list = None,
        keda_config: Dict[str, Any] = None
    ) -> bool:
        if ports is None:
            ports = [80]
        if keda_config is None:
            keda_config = {}

        try:
            deployment = {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": name, "namespace": self.namespace},
                "spec": {
                    "replicas": replicas,
                    "selector": {"matchLabels": {"app": name}},
                    "template": {
                        "metadata": {"labels": {"app": name}},
                        "spec": {
                            "containers": [{
                                "name": name,
                                "image": f"{image}:{tag}",
                                "ports": [{"containerPort": p} for p in ports],
                                "resources": {
                                    "requests": {
                                        "cpu": cpu_request,
                                        "memory": memory_request
                                    },
                                    "limits": {
                                        "cpu": cpu_limit,
                                        "memory": memory_limit
                                    }
                                }
                            }]
                        }
                    }
                }
            }

            deployment_file = f"{name}-deployment.yaml"
            with open(deployment_file, 'w') as f:
                yaml.dump(deployment, f)

            cmd = f"kubectl apply -f {deployment_file}"
            if self.kubeconfig:
                cmd += f" --kubeconfig={self.kubeconfig}"
            self.run_command(cmd)

            if ports:
                service = {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {"name": f"{name}-service", "namespace": self.namespace},
                    "spec": {
                        "selector": {"app": name},
                        "ports": [{"port": p, "targetPort": p} for p in ports],
                        "type": "ClusterIP"
                    }
                }

                service_file = f"{name}-service.yaml"
                with open(service_file, 'w') as f:
                    yaml.dump(service, f)

                cmd = f"kubectl apply -f {service_file}"
                if self.kubeconfig:
                    cmd += f" --kubeconfig={self.kubeconfig}"
                self.run_command(cmd)

            if keda_config and self.keda_installed:
                scaled_object = {
                    "apiVersion": "keda.sh/v1alpha1",
                    "kind": "ScaledObject",
                    "metadata": {
                        "name": f"{name}-scaled",
                        "namespace": self.namespace
                    },
                    "spec": {
                        "scaleTargetRef": {
                            "apiVersion": "apps/v1",
                            "kind": "Deployment",
                            "name": name
                        },
                        "minReplicaCount": keda_config.get("min_replicas", 1),
                        "maxReplicaCount": keda_config.get("max_replicas", 10),
                        "triggers": keda_config.get("triggers", [])
                    }
                }

                scaled_object_file = f"{name}-scaledobject.yaml"
                with open(scaled_object_file, 'w') as f:
                    yaml.dump(scaled_object, f)

                cmd = f"kubectl apply -f {scaled_object_file}"
                if self.kubeconfig:
                    cmd += f" --kubeconfig={self.kubeconfig}"
                self.run_command(cmd)

            print(f"Deployment '{name}' created successfully")
            return True
        except Exception as e:
            print(f"Failed to create deployment: {str(e)}")
            return False

    def get_deployment_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get health status of a deployment."""
        try:
            cmd = f"kubectl get deployment {name} -n {self.namespace} -o json"
            if self.kubeconfig:
                cmd += f" --kubeconfig={self.kubeconfig}"
            result = self.run_command(cmd)
            
            deployment = json.loads(result.stdout)
            status = {
                "name": name,
                "ready_replicas": deployment["status"].get("readyReplicas", 0),
                "available_replicas": deployment["status"].get("availableReplicas", 0),
                "unavailable_replicas": deployment["status"].get("unavailableReplicas", 0),
                "conditions": deployment["status"].get("conditions", [])
            }
            
            cmd = f"kubectl get pods -n {self.namespace} -l app={name} -o json"
            if self.kubeconfig:
                cmd += f" --kubeconfig={self.kubeconfig}"
            result = self.run_command(cmd)
            pods = json.loads(result.stdout)
            
            pod_statuses = []
            for pod in pods["items"]:
                pod_status = {
                    "name": pod["metadata"]["name"],
                    "status": pod["status"]["phase"],
                    "ready": all(c["ready"] for c in pod["status"].get("containerStatuses", [])),
                    "restarts": sum(c["restartCount"] for c in pod["status"].get("containerStatuses", []))
                }
                pod_statuses.append(pod_status)
            
            status["pods"] = pod_statuses
            return status
        except Exception as e:
            print(f"Failed to get deployment status: {str(e)}")
            return None

def main():
    parser = argparse.ArgumentParser(description="Kubernetes Cluster Automation Tool")
    parser.add_argument("--kubeconfig", help="Path to kubeconfig file")
    parser.add_argument("--namespace", default="default", help="Kubernetes namespace to use")
    
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Connect cmd
    connect_parser = subparsers.add_parser("connect", help="Connect to Kubernetes cluster")
    
    # Install tools cmd
    install_parser = subparsers.add_parser("install", help="Install tools")
    install_parser.add_argument("--helm", action="store_true", help="Install Helm")
    install_parser.add_argument("--keda", action="store_true", help="Install KEDA")
    
    # Create deployment cmd
    deploy_parser = subparsers.add_parser("deploy", help="Create a deployment")
    deploy_parser.add_argument("name", help="Deployment name")
    deploy_parser.add_argument("image", help="Docker image name")
    deploy_parser.add_argument("--tag", default="latest", help="Image tag")
    deploy_parser.add_argument("--replicas", type=int, default=1, help="Initial replicas")
    deploy_parser.add_argument("--cpu-request", default="100m", help="CPU request")
    deploy_parser.add_argument("--cpu-limit", default="500m", help="CPU limit")
    deploy_parser.add_argument("--memory-request", default="128Mi", help="Memory request")
    deploy_parser.add_argument("--memory-limit", default="512Mi", help="Memory limit")
    deploy_parser.add_argument("--ports", nargs="+", type=int, default=[80], help="Ports to expose")
    deploy_parser.add_argument("--keda-config", help="Path to KEDA config JSON file")
    
    # Status cmd
    status_parser = subparsers.add_parser("status", help="Get deployment status")
    status_parser.add_argument("name", help="Deployment name")
    
    args = parser.parse_args()

    k8s = KubernetesAutomation(args.kubeconfig, args.namespace)

    if args.command == "connect":
        if not k8s.connect_to_cluster():
            exit(1)
    
    elif args.command == "install":
        if args.helm:
            if not k8s.install_helm():
                exit(1)
        if args.keda:
            if not k8s.install_keda():
                exit(1)
    
    elif args.command == "deploy":
        keda_config = {}
        if args.keda_config:
            try:
                with open(args.keda_config) as f:
                    keda_config = json.load(f)
            except Exception as e:
                print(f"Failed to load KEDA config: {str(e)}")
                exit(1)
        
        success = k8s.create_deployment(
            name=args.name,
            image=args.image,
            tag=args.tag,
            replicas=args.replicas,
            cpu_request=args.cpu_request,
            cpu_limit=args.cpu_limit,
            memory_request=args.memory_request,
            memory_limit=args.memory_limit,
            ports=args.ports,
            keda_config=keda_config
        )
        if not success:
            exit(1)
    
    elif args.command == "status":
        status = k8s.get_deployment_status(args.name)
        if status:
            print(json.dumps(status, indent=2))
        else:
            exit(1)

if __name__ == "__main__":
    main()
