import fileinput
import os
import re
import subprocess
import sys
from pathlib import Path

# Assumes the script is run from the project root
PROJECT_ROOT = Path(__file__).parent.resolve()
SRC_DIR = PROJECT_ROOT / "src"
PROTO_DIR = SRC_DIR / "etcd3" / "proto"
ETCDRPC_DIR = SRC_DIR / "etcd3" / "etcdrpc"
RPC_PROTO_FILE = PROTO_DIR / "rpc.proto"
RPC_PB2_FILE = ETCDRPC_DIR / "rpc_pb2.py"
RPC_PB2_GRPC_FILE = ETCDRPC_DIR / "rpc_pb2_grpc.py"


def sed_inplace(file_path, pattern, replacement):
    """
    Performs sed-like in-place replacement on a file.
    """
    with fileinput.FileInput(file_path, inplace=True, encoding="utf-8") as file:
        for line in file:
            print(re.sub(pattern, replacement, line), end="")


def main():
    """
    Generate protobuf files.
    This script replaces the genproto environment in tox.ini.
    """
    try:
        from grpc.tools import protoc
    except ImportError:
        print(
            "Error: 'grpcio-tools' is not installed or not found in the current environment.",
            file=sys.stderr,
        )
        print(
            "Please install the required dependencies by running: pip install -e .[protoc]",
            file=sys.stderr,
        )
        sys.exit(1)

    print("--- Modifying rpc.proto before generation ---")

    # Read rpc.proto and apply modifications
    with open(RPC_PROTO_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    modified_lines = []
    skip_lines = 0
    for line in lines:
        if skip_lines > 0:
            skip_lines -= 1
            continue

        # /gogoproto/d
        if "gogoproto" in line:
            print(f"Dropping line: {line.strip()}")
            continue

        # /google\/api\/annotations.proto/d
        if "google/api/annotations.proto" in line:
            print(f"Dropping line: {line.strip()}")
            continue

        # /option (google.api.http)/,+3d
        if "option (google.api.http)" in line:
            print(f"Dropping http option block starting with: {line.strip()}")
            skip_lines = 3
            continue
        
        # s/etcd\/mvcc\/mvccpb\/kv.proto/kv.proto/g
        line = line.replace("etcd/mvcc/mvccpb/kv.proto", "kv.proto")
        # s/etcd\/auth\/authpb\/auth.proto/auth.proto/g
        line = line.replace("etcd/auth/authpb/auth.proto", "auth.proto")

        modified_lines.append(line)

    with open(RPC_PROTO_FILE, "w", encoding="utf-8") as f:
        f.writelines(modified_lines)

    print("--- Running protoc ---")

    # Ensure output directory exists
    ETCDRPC_DIR.mkdir(exist_ok=True)

    # python -m grpc.tools.protoc ...
    protoc_command = [
        sys.executable,
        "-m",
        "grpc.tools.protoc",
        f"-I{PROTO_DIR}",
        f"--python_out={ETCDRPC_DIR}",
        f"--grpc_python_out={ETCDRPC_DIR}",
        str(PROTO_DIR / "rpc.proto"),
        str(PROTO_DIR / "auth.proto"),
        str(PROTO_DIR / "kv.proto"),
    ]
    print(f"Running: {' '.join(protoc_command)}")
    result = subprocess.run(protoc_command, check=False, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        print("protoc command failed:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(result.returncode)
    
    print(result.stdout)
    if result.stderr:
        print("protoc stderr:")
        print(result.stderr)


    # Create __init__.py if it doesn't exist
    (ETCDRPC_DIR / "__init__.py").touch(exist_ok=True)

    print("--- Modifying generated python files ---")

    # sed -i -e 's/import auth_pb2/from etcd3.etcdrpc import auth_pb2/g' etcd3/etcdrpc/rpc_pb2.py
    # sed -i -e 's/import kv_pb2/from etcd3.etcdrpc import kv_pb2/g' etcd3/etcdrpc/rpc_pb2.py
    if RPC_PB2_FILE.exists():
        print(f"Patching imports in {RPC_PB2_FILE}")
        sed_inplace(RPC_PB2_FILE, r"^import auth_pb2", "from etcd3.etcdrpc import auth_pb2")
        sed_inplace(RPC_PB2_FILE, r"^import kv_pb2", "from etcd3.etcdrpc import kv_pb2")
    else:
        print(f"Warning: {RPC_PB2_FILE} not found for patching.")


    # sed -i -e 's/import rpc_pb2/from etcd3.etcdrpc import rpc_pb2/g' etcd3/etcdrpc/rpc_pb2_grpc.py
    if RPC_PB2_GRPC_FILE.exists():
        print(f"Patching imports in {RPC_PB2_GRPC_FILE}")
        sed_inplace(RPC_PB2_GRPC_FILE, r"^import rpc_pb2", "from etcd3.etcdrpc import rpc_pb2")
    else:
        print(f"Warning: {RPC_PB2_GRPC_FILE} not found for patching.")


    print("Proto files generated successfully.")


if __name__ == "__main__":
    main()