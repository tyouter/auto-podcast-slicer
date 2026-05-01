import sys
import shutil
import argparse
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = FRAMEWORK_ROOT / "templates"
PROJECTS_REGISTRY = FRAMEWORK_ROOT / "projects.yaml"


def create_project(name: str, template: str, target_dir: str | None = None):
    template_dir = TEMPLATES_DIR / template
    if not template_dir.exists():
        print(f"Template not found: {template}")
        print(f"Available: {[d.name for d in TEMPLATES_DIR.iterdir() if d.is_dir()]}")
        sys.exit(1)

    if target_dir:
        project_dir = Path(target_dir)
    else:
        project_dir = FRAMEWORK_ROOT.parent / name

    if project_dir.exists():
        print(f"Directory already exists: {project_dir}")
        sys.exit(1)

    shutil.copytree(template_dir, project_dir)

    project_yaml = project_dir / "project.yaml"
    if project_yaml.exists():
        import yaml
        with open(project_yaml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        data["name"] = name
        if not data.get("output", {}).get("base_dir"):
            data.setdefault("output", {})
            data["output"]["base_dir"] = str(project_dir / "output")
        with open(project_yaml, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    _register_project(name, str(project_dir), template)

    print(f"Project created: {project_dir}")
    print(f"  project.yaml: {project_dir / 'project.yaml'}")
    print(f"  corrections.yaml: {project_dir / 'corrections.yaml'}")
    print()
    print("Next steps:")
    print(f"  1. Edit {project_dir / 'project.yaml'} to set sources and clips")
    print(f"  2. Run: python make_short_videos_v2.py --project {project_dir}")


def list_templates():
    print("Available templates:")
    for d in sorted(TEMPLATES_DIR.iterdir()):
        if d.is_dir():
            project_yaml = d / "project.yaml"
            if project_yaml.exists():
                import yaml
                with open(project_yaml, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                desc = data.get("description", "(no description)")
                name = data.get("name", d.name)
                print(f"  {d.name}: {name} — {desc}")
            else:
                print(f"  {d.name}: (no project.yaml)")


def list_projects():
    if not PROJECTS_REGISTRY.exists():
        print("No projects registered yet.")
        return

    import yaml
    with open(PROJECTS_REGISTRY, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    projects = data.get("projects", [])
    if not projects:
        print("No projects registered yet.")
        return

    print(f"Registered projects ({len(projects)}):")
    for p in projects:
        print(f"  {p['name']}: {p['path']} (template: {p.get('template', 'unknown')})")


def _register_project(name: str, path: str, template: str):
    import yaml

    data = {}
    if PROJECTS_REGISTRY.exists():
        with open(PROJECTS_REGISTRY, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    projects = data.get("projects", [])
    for p in projects:
        if p["name"] == name:
            p["path"] = path
            p["template"] = template
            break
    else:
        projects.append({"name": name, "path": path, "template": template})

    data["projects"] = projects
    with open(PROJECTS_REGISTRY, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def main():
    parser = argparse.ArgumentParser(description="Garden AutoResearch Project Manager")
    sub = parser.add_subparsers(dest="command")

    create_p = sub.add_parser("create", help="Create a new project from template")
    create_p.add_argument("name", help="Project name")
    create_p.add_argument("--template", "-t", default="blank", help="Template name (default: blank)")
    create_p.add_argument("--dir", "-d", help="Target directory (default: ../<name>)")

    sub.add_parser("templates", help="List available templates")
    sub.add_parser("list", help="List registered projects")

    args = parser.parse_args()

    if args.command == "create":
        create_project(args.name, args.template, args.dir)
    elif args.command == "templates":
        list_templates()
    elif args.command == "list":
        list_projects()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
