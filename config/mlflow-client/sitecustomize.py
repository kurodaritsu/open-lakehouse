"""Let MLflow register models into Unity Catalog OSS on top of SeaweedFS.

`MLFLOW_REGISTRY_URI=uc:...` uploads model versions through
`OptimizedS3ArtifactRepository`, which asks HeadBucket for the bucket region
and raises when there's none. SeaweedFS (4.47) never returns one, so fall back
to `AWS_REGION` / `AWS_DEFAULT_REGION` / `us-east-1`.

Loaded through PYTHONPATH. The patch hooks the module import instead of
importing mlflow here, so Python startup stays cheap for everything else.
"""

import os
import sys
from importlib.abc import MetaPathFinder
from importlib.machinery import PathFinder

_TARGET = "mlflow.store.artifact.optimized_s3_artifact_repo"


def _patch(module):
    repo = module.OptimizedS3ArtifactRepository
    original = repo._get_region_name

    def _get_region_name(self):
        # ponytail: patches a private method, recheck on MLflow bumps. Drop once
        # SeaweedFS returns `x-amz-bucket-region` or MLflow falls back itself.
        try:
            return original(self)
        except Exception:
            return (
                os.environ.get("AWS_REGION")
                or os.environ.get("AWS_DEFAULT_REGION")
                or "us-east-1"
            )

    repo._get_region_name = _get_region_name


class _PatchOnImport(MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name != _TARGET:
            return None
        spec = PathFinder.find_spec(name, path)
        if spec is None or spec.loader is None:
            return spec
        exec_module = spec.loader.exec_module

        def _exec_and_patch(module):
            exec_module(module)
            _patch(module)

        spec.loader.exec_module = _exec_and_patch
        return spec


sys.meta_path.insert(0, _PatchOnImport())
