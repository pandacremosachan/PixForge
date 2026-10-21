"""Copy text templates into a NEW task directory. No software or project edits."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", nargs="?")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--namespace", default="examplemod")
    parser.add_argument("--name", default="new_asset")
    parser.add_argument("--dependency", action="append", default=[], type=Path)
    parser.add_argument("--project-source", action="append", default=[], type=Path)
    args = parser.parse_args(argv)
    try:
        catalog = json.loads((ROOT / "assets/workflows.json").read_text(encoding="utf-8"))
        if args.list:
            print(json.dumps(catalog, ensure_ascii=False, indent=2))
            return 0
        recipe = next((r for r in catalog["recipes"] if r["id"] == args.recipe), None)
        if recipe is None or args.output is None:
            parser.error("choose a recipe from --list and supply --output NEW_DIRECTORY")
        if not re.fullmatch(r"[a-z0-9_][a-z0-9_.-]*", args.namespace):
            raise ValueError("namespace must use lowercase resource characters")
        if (not re.fullmatch(r"[a-z0-9_./-]+", args.name)
                or any(p in ("", ".", "..") for p in args.name.split("/"))):
            raise ValueError("name must be a lowercase resource path without traversal")
        sources = []
        for role, paths in (("dependency", args.dependency), ("project", args.project_source)):
            for path in paths:
                path = path.expanduser().resolve()
                if not path.exists():
                    raise ValueError("resource source does not exist: " + str(path))
                sources.append({"name": role + "-" + str(len(sources) + 1), "path": str(path), "role": role})
        content = {}
        for file in sorted((ROOT / recipe["template"]).rglob("*")):
            if not file.is_file():
                continue
            relative = file.relative_to(ROOT / recipe["template"])
            text = file.read_text(encoding="utf-8").replace("${namespace}", args.namespace).replace("${name}", args.name)
            if file.suffix == ".json":
                data = json.loads(text)
                if file.name == "target.json":
                    data["sources"] = sources
                text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            content[relative] = text
        destination = args.output.expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=False)
        for relative, text in content.items():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
        print(json.dumps({"recipe": recipe["id"], "directory": str(destination), "workflow": recipe["workflow"],
                          "files": [str(p) for p in content], "starter_only": True,
                          "software_started": False, "export_approved": False}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"error": str(error), "code": "SCAFFOLD_ERROR"}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
