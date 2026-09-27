"""Compare preserved execution source directly; never trust an equality flag file."""

import ast
from pathlib import Path

from .contracts import Frozen
from .data import sha256


class SourceEvidence(Frozen):
    snapshot_sha256: dict[str, str]
    local_worker_sha256: str
    local_contracts_sha256: str
    verified_declarations: tuple[str, ...]


def declaration(tree: ast.Module, name: str) -> ast.stmt:
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == name:
            return node
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name
                                                for target in node.targets):
            return node
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return node
    raise ValueError("Required declaration absent from preserved source")


def remove_admission(function: ast.FunctionDef) -> ast.FunctionDef:
    """Allow only the observed registry call or a side-effect-free legacy rejection guard."""
    current = ast.parse("validate_device(os.environ)").body[0]
    if ast.dump(function.body[0]) == ast.dump(current):
        function.body = function.body[1:]
        return function
    assignment = ast.parse('visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")').body[0]
    if ast.dump(function.body[0]) != ast.dump(assignment):
        raise ValueError("Unrecognized accelerator admission statement")
    guard = function.body[1]
    if not isinstance(guard, ast.If) or guard.orelse or len(guard.body) != 1:
        raise ValueError("Admission guard contains additional execution")
    rejection = guard.body[0]
    if (not isinstance(rejection, ast.Raise) or not isinstance(rejection.exc, ast.Call)
            or not isinstance(rejection.exc.func, ast.Name) or rejection.exc.func.id != "ValueError"
            or len(rejection.exc.args) != 1 or not isinstance(rejection.exc.args[0], ast.Constant)
            or rejection.exc.keywords or rejection.cause is not None):
        raise ValueError("Admission guard does not only reject invalid configuration")
    allowed = (ast.BoolOp, ast.UnaryOp, ast.Compare, ast.Name, ast.Load, ast.Constant, ast.Set,
               ast.Or, ast.And, ast.Not, ast.In, ast.NotIn, ast.Call, ast.Attribute)
    strip = ast.parse("visible.strip()", mode="eval").body
    for node in ast.walk(guard.test):
        if not isinstance(node, allowed):
            raise TypeError("Admission guard contains a non-policy expression")
        if isinstance(node, ast.Name) and node.id != "visible":
            raise ValueError("Admission guard reads unrelated state")
        if isinstance(node, ast.Call) and ast.dump(node) != ast.dump(strip):
            raise ValueError("Admission guard executes an unrelated call")
    function.body = function.body[2:]
    return function


def verify_sources(directory: Path, recorded: dict[str, str]) -> SourceEvidence:
    snapshot = directory / "source_snapshot" / "benchmarks" / "forecast" / "public_bank"
    local = Path(__file__).parent
    if any(sha256(snapshot / name) != expected for name, expected in recorded.items()):
        raise ValueError("Preserved execution source differs from runtime hashes")
    if sha256(local / "data.py") != recorded["data.py"]:
        raise ValueError("Worker data dependency changed since execution")
    old_worker = ast.parse((snapshot / "worker.py").read_bytes())
    new_worker = ast.parse((local / "worker.py").read_bytes())
    checked = []
    for name in ("RunConfig", "CONFIGS", "weight_hash", "predict", "save_inference", "run"):
        before = declaration(old_worker, name)
        after = declaration(new_worker, name)
        if name == "run":
            if not isinstance(before, ast.FunctionDef) or not isinstance(after, ast.FunctionDef):
                raise ValueError("Worker entry is not a function")
            before, after = remove_admission(before), remove_admission(after)
        if ast.dump(before) != ast.dump(after):
            raise ValueError("Executed worker calculations differ from reviewed source")
        checked.append(f"worker.{name}")
    old_contracts = ast.parse((snapshot / "contracts.py").read_bytes())
    new_contracts = ast.parse((local / "contracts.py").read_bytes())
    for name in ("Split", "Frozen", "Case", "TrainingSeries", "Inputs", "Prediction"):
        if ast.dump(declaration(old_contracts, name)) != ast.dump(declaration(new_contracts, name)):
            raise ValueError("Worker contract dependency differs from preserved execution source")
        checked.append(f"contracts.{name}")
    return SourceEvidence(snapshot_sha256=recorded, local_worker_sha256=sha256(local / "worker.py"),
                          local_contracts_sha256=sha256(local / "contracts.py"),
                          verified_declarations=tuple(checked))
