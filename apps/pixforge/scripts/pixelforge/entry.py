"""Private entry of the shared application process."""
import argparse


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("serve",))
    parser.add_argument("--workspace")
    parser.add_argument("--runtime")
    parser.add_argument("--workbench", action="store_true")
    args = parser.parse_args(argv)
    from .service import serve
    return serve(workspace=args.workspace, runtime=args.runtime, workbench=args.workbench)
