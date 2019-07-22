import logging
from pathlib import Path
from uuid import UUID, uuid5

import docker

from ._config import Config

LOG = logging.getLogger(__name__)


class LambdaBuild:
    NULL_UUID = UUID("{00000000-0000-0000-0000-000000000000}")

    def __init__(self, config: Config, build_submodules=True):
        self._docker = docker.from_env()
        self._config = config
        self._build_lambdas(config.lambda_source_path, config.lambda_zip_path)
        if build_submodules:
            rel_source = config.lambda_source_path.relative_to(config.project_root)
            rel_zip = config.lambda_zip_path.relative_to(config.project_root)
            self._recurse(config.project_root, rel_source, rel_zip)

    def _recurse(self, base_path, rel_source, rel_zip):
        submodules_path = Path(base_path) / "submodules"
        if submodules_path.is_dir():
            for submodule in submodules_path.iterdir():
                source_path = submodule / rel_source
                output_path = submodule / rel_zip
                if source_path.is_dir():
                    self._build_lambdas(source_path, output_path)
                self._recurse(submodule, rel_source, rel_zip)

    def _build_lambdas(self, parent_path: Path, output_path):
        if parent_path.is_dir:
            for path in parent_path.iterdir():
                if (path / "Dockerfile").is_file():
                    tag = f"taskcat-build-{uuid5(self.NULL_UUID, str(path)).hex}"
                    LOG.info(
                        f"Packaging lambda source from {path} using docker image {tag}"
                    )
                    self._docker_build(path, tag)
                    self._docker_extract(tag, output_path / path.stem)

    @staticmethod
    def _clean_build_log(line):
        if "stream" in line:
            line = line["stream"]
        elif "aux" in line:
            line = line["aux"]
        return str(line).strip()

    def _docker_build(self, path, tag):
        _, logs = self._docker.images.build(path=str(path), tag=tag)
        build_logs = []
        for line in logs:
            line = self._clean_build_log(line)
            if line:
                build_logs.append(line)
        LOG.debug("docker build logs: \n{}".format("\n".join(build_logs)))

    def _docker_extract(self, tag, package_path):
        volumes = {str(package_path): {"bind": "/output", "mode": "rw"}}
        logs = self._docker.containers.run(image=tag, auto_remove=True, volumes=volumes)
        LOG.debug("docker run logs: \n{}".format(logs.decode("utf-8").strip()))
