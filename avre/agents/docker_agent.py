
import docker
import os
import time
import requests
from pathlib import Path
from avre.config import DOCKER_IMAGE_TAG, VULN_PORT, FIXED_PORT
from avre.utils.logger import get_logger

class DockerAgent:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.logger = get_logger("DockerAgent", session_id)
        try:
            self.client = docker.from_env()
        except Exception as e:
            self.logger.error(f"Docker is not running: {e}")
            raise

    def generate_dockerfile(self, workspace_path: Path):
        self.logger.info(f"Generating Dockerfile for {workspace_path}")
        
        # Simple detection logic (expandable)
        if (workspace_path / "package.json").exists():
            # Check for legacy bcrypt
            with open(workspace_path / "package.json", "r", encoding="utf-8") as f:
                content = f.read().lower()
                
            base_image = "node:18-alpine"
            install_cmd = "RUN npm install --ignore-scripts --legacy-peer-deps"
            
            if '"bcrypt": "^1' in content or '"bcrypt": "1' in content:
                # We patch bcrypt -> bcryptjs in GitAgent now, so we can use modern Node!
                self.logger.info("Legacy bcrypt detected, but it should be patched to bcryptjs. Using modern Node 18.")
                # We can stick to standard image
                pass 

            content = f"""
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
# Legacy peer deps often needed for older repos like NodeGoat
RUN npm install --ignore-scripts --legacy-peer-deps
COPY . .
ENV PORT=3000
EXPOSE 3000
CMD ["npm", "start"]
"""
        elif (workspace_path / "requirements.txt").exists():
             content = """
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV PORT=3000
EXPOSE 3000
CMD ["python", "app.py"]
"""
        else:
            self.logger.warning("Unknown project type. Defaulting to Node.")
            content = """
FROM node:18-alpine
WORKDIR /app
COPY . .
RUN npm install
ENV PORT=3000
EXPOSE 3000
CMD ["npm", "start"]
"""
        
        with open(workspace_path / "Dockerfile", "w") as f:
            f.write(content.strip())

    def build_image(self, workspace_path: Path, tag_suffix: str):
        full_tag = f"{DOCKER_IMAGE_TAG}-{tag_suffix}"
        self.logger.info(f"Building image {full_tag} from {workspace_path}...")
        
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                self.client.images.build(path=str(workspace_path), tag=full_tag, rm=True)
                self.logger.info(f"Image {full_tag} built successfully.")
                return full_tag
            except (docker.errors.BuildError, docker.errors.APIError) as e:
                # If build fails, it might be transient or permanent.
                # If 1st attempt, maybe just retry.
                if attempt < MAX_RETRIES - 1:
                    wait_time = (attempt + 1) * 3
                    self.logger.warning(f"Build failed ({e}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Build failed after {MAX_RETRIES} attempts: {e}")
                    raise

    def setup_network(self):
        try:
            self.client.networks.get("avre-net")
        except docker.errors.NotFound:
            self.client.networks.create("avre-net", driver="bridge")

    def start_database(self, db_type="mongo"):
        try:
            # 1. Clean up stale database containers
            known_dbs = ["avre-mongo"]
            target_container_name = "avre-mongo"
            
            for db_name in known_dbs:
                try:
                    c = self.client.containers.get(db_name)
                    if c.status != "running":
                        c.remove(force=True)
                    else:
                        # Already running? Check if it's our target
                        if db_name == target_container_name:
                             self.logger.info("Database avre-mongo is already running.")
                             return
                except docker.errors.NotFound:
                    pass

            image = "mongo:4.4"
            self.logger.info("Starting shared mongo container...")
            container = self.client.containers.run(
                image,
                name=target_container_name,
                detach=True,
                network="avre-net",
                hostname=target_container_name
            )
            
            # Optimized wait: Poll for readiness
            self.logger.info("Waiting for mongo to be ready...")
            start = time.time()
            timeout = 30
            while time.time() - start < timeout:
                if container.status == "exited":
                     raise Exception(f"Database container exited prematurely. Logs: {container.logs().decode('utf-8')}")
                
                try:
                    logs = container.logs().decode('utf-8')
                    if "Waiting for connections" in logs:
                         return
                except:
                    pass
                time.sleep(1)
            
            self.logger.warning(f"Database wait timeout ({timeout}s). Proceeding anyway.")
            
        except Exception as e:
            self.logger.error(f"Failed to start database: {e}")
            raise

    def run_container(self, image_tag: str, port: int, name: str):
        self.logger.info(f"Starting container {name} on port {port}...")
        
        # Cleanup existing
        try:
            old = self.client.containers.get(name)
            old.stop()
            old.remove()
        except docker.errors.NotFound:
            pass

        # Env vars for DB connection
        # We inject both Mongo and MySQL vars to be safe/lazy
        env = {
            "PORT": 3000,
            # Mongo
            "MONGODB_URI": "mongodb://avre-mongo:27017/nodegoat",
            "DB_URL": "mongodb://avre-mongo:27017/nodegoat"
        }

        container = self.client.containers.run(
            image_tag,
            ports={'3000/tcp': port},
            name=name,
            detach=True,
            network="avre-net",
            environment=env
        )
        return container
        
        
    def wait_for_health(self, port: int, container_name: str, timeout: int = 90):
        url = f"http://localhost:{port}"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 1. Check if container is still running
            try:
                container = self.client.containers.get(container_name)
                if container.status != "running":
                    logs = container.logs().decode('utf-8')
                    self.logger.error(f"Container {container_name} crashed/exited prematurely. Logs:\n{logs[-500:]}")
                    return False
            except Exception as e:
                self.logger.warning(f"Could not check container status: {e}")

            # 2. Check HTTP health
            try:
                requests.get(url, timeout=2)
                self.logger.info(f"Health check passed for {url}")
                return True
            except requests.RequestException:
                time.sleep(1)
        
        self.logger.error(f"Health check failed for {url} after {timeout}s")
        # Log container logs for debugging timeout
        try:
             c = self.client.containers.get(container_name)
             self.logger.error(f"Container logs:\n{c.logs().decode('utf-8')[-500:]}")
        except: pass
        return False

    def cleanup(self, names: list):
        for name in names:
            try:
                c = self.client.containers.get(name)
                c.stop()
                c.remove()
                self.logger.info(f"Cleaned up container {name}")
            except:
                pass
