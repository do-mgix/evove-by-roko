"""Register attributes in the graph.

Every command applies to the database and writes the same change into
backend/data/attributes_tree.json, so a fresh install builds the same graph.

    show KEY
    subdivide PARENT KEY=Name:weight [KEY=Name:weight ...]   a leaf gets children
    add PARENT KEY=Name:weight [...]                          more children, parent keeps its value
    link PARENT CHILD WEIGHT                                  a non-primary link
    reweight PARENT CHILD=weight [...]                        set every child's weight
    root KEY Name                                             a parentless attribute
    code-for PARENT                                           the code a new action would get

Run from the repository root with DATABASE_URL set:

    DATABASE_URL=mysql+pymysql://roko:rokopass@127.0.0.1:3306/roko?charset=utf8mb4 \\
      python backend/scripts/attributes.py subdivide biceps c_longa="Cabeça longa":0.6 c_curta="Cabeça curta":0.4
"""
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from src.domain.attributes import RegistrationError  # noqa: E402
from src.infrastructure import repos  # noqa: E402

SEED = BACKEND / "data" / "attributes_tree.json"


# ---------------------------------------------------------------- seed file

def _line(obj: dict) -> str:
    body = json.dumps(obj, ensure_ascii=False)
    return "    { " + body[1:-1] + " }"


def _write_seed(seed: dict) -> None:
    """Same layout as the hand-kept file: one object per line, a blank line
    between groups."""
    def block(name, items, group):
        lines, prev = [], None
        for i, o in enumerate(items):
            g = group(o)
            if i and g != prev:
                lines.append("")
            prev = g
            lines.append(_line(o))
        last = max(i for i, l in enumerate(lines) if l)
        out = [l + ("," if l and i != last else "") for i, l in enumerate(lines)]
        return f'  "{name}": [\n' + "\n".join(out) + "\n  ]"

    parent = {e["child"]: e["parent"] for e in seed["edges"] if e.get("primary", True)}

    def root(k):
        while k in parent:
            k = parent[k]
        return k

    text = "{\n" + ",\n\n".join([
        block("nodes", seed["nodes"], lambda o: root(o["key"])),
        block("edges", seed["edges"], lambda o: o["parent"]),
        block("contributions", seed["contributions"], lambda o: o["action"]),
        block("action_templates", seed["action_templates"], lambda o: None),
    ]) + "\n}\n"
    json.loads(text)
    SEED.write_text(text, encoding="utf-8")


def _seed() -> dict:
    return json.loads(SEED.read_text(encoding="utf-8"))


def _settings(node: dict) -> dict:
    return {k: node[k] for k in ("half_life_hours", "floor", "threshold", "max_level") if k in node}


def _insert_after(items: list, pred, new: list) -> None:
    idx = max((i for i, o in enumerate(items) if pred(o)), default=len(items) - 1)
    items[idx + 1:idx + 1] = new


# ---------------------------------------------------------------- commands

def _parse_children(args):
    out = []
    for a in args:
        key, _, rest = a.partition("=")
        name, _, weight = rest.rpartition(":")
        if not key or not name or not weight:
            raise SystemExit(f"expected KEY=Name:weight, got '{a}'")
        out.append((key, name, float(weight)))
    return out


def cmd_subdivide(parent, *specs):
    children = _parse_children(specs)
    result = repos.subdivide_attribute(parent, children)
    seed = _seed()
    pnode = next(n for n in seed["nodes"] if n["key"] == parent)
    _insert_after(seed["nodes"], lambda n: n["key"] == parent,
                  [{"key": k, "name": nm, **_settings(pnode)} for k, nm, _ in children])
    seed["edges"].extend({"parent": parent, "child": k, "weight": w} for k, _, w in children)
    moved = []
    for c in seed["contributions"]:
        if c["leaf"] == parent:
            moved += [{"action": c["action"], "leaf": k, "weight": c["weight"]} for k, _, _ in children]
        else:
            moved.append(c)
    seed["contributions"] = moved
    _write_seed(seed)
    print(f"{parent}: {result['children']} filhos; herdaram {result['scores']} scores "
          f"e {result['contributions']} contribuições")


def cmd_add(parent, *specs):
    children = _parse_children(specs)
    result = repos.add_attribute_children(parent, children)
    seed = _seed()
    for e in seed["edges"]:
        if e["parent"] == parent:
            e["weight"] = round(e["weight"] * result["scaled_by"], 6)
    sibling = next(n for n in seed["nodes"] if n["key"] == next(e["child"] for e in seed["edges"] if e["parent"] == parent))
    _insert_after(seed["nodes"], lambda n: any(e["child"] == n["key"] and e["parent"] == parent for e in seed["edges"]),
                  [{"key": k, "name": nm, **_settings(sibling)} for k, nm, _ in children])
    seed["edges"].extend({"parent": parent, "child": k, "weight": w} for k, _, w in children)
    _write_seed(seed)
    print(f"{parent}: +{result['children']} filhos; os existentes escalados por {result['scaled_by']}; "
          f"{result['users']} perfis começaram os novos no valor atual do pai")


def cmd_link(parent, child, weight):
    result = repos.link_attribute(parent, child, float(weight))
    seed = _seed()
    seed["edges"].append({"parent": parent, "child": child, "weight": float(weight), "primary": False})
    _write_seed(seed)
    total = result["weight_total"]
    note = "" if abs(total - 1) < 1e-3 else f"  (pesos de {parent} somam {total}; continue ligando até dar 1)"
    print(f"{parent} -> {child} ({weight}){note}")


def cmd_reweight(parent, *specs):
    weights = {}
    for s in specs:
        k, _, w = s.partition("=")
        weights[k] = float(w)
    repos.reweight_attribute(parent, weights)
    seed = _seed()
    for e in seed["edges"]:
        if e["parent"] == parent and e["child"] in weights:
            e["weight"] = weights[e["child"]]
    _write_seed(seed)
    print(f"{parent}: pesos atualizados")


def cmd_root(key, name):
    repos.create_root(key, name)
    seed = _seed()
    seed["nodes"].append({"key": key, "name": name})
    _write_seed(seed)
    print(f"raiz {key} criada")


def cmd_show(key):
    tree = repos.load_attr_tree()
    if key not in tree.nodes_by_key:
        raise SystemExit(f"unknown attribute '{key}'")
    n = tree.nodes_by_key[key]
    print(f"{n.name} [{key}]  grau {tree.degree(key)}  {'folha' if tree.is_leaf(key) else 'interno'}")
    print("  caminho:", " → ".join(tree.nodes_by_key[k].name for k in tree.primary_chain(key)))
    for p, w, prim in tree.parents.get(key, []):
        print(f"  pai {'primário ' if prim else ''}{tree.nodes_by_key[p].name} ({w})")
    for c, w in tree.children.get(key, []):
        print(f"  filho {tree.nodes_by_key[c].name} ({w})")


def cmd_code_for(parent):
    r = repos.code_for_parent(parent)
    tree = repos.load_attr_tree()
    c = r["code"]
    names = tree.nodes_by_key[r["class1"]].name + (" · " + tree.nodes_by_key[r["class2"]].name if r["class2"] else "")
    flags = [f for f, on in (("classe¹ nova", r["new_class1"]), ("classe² nova", r["new_class2"])) if on]
    print(f"{c[0]} {c[1:3]} {c[3:5]} {c[5:]}   {names}" + (f"   ({', '.join(flags)})" if flags else ""))


COMMANDS = {"show": cmd_show, "subdivide": cmd_subdivide, "add": cmd_add, "link": cmd_link,
            "reweight": cmd_reweight, "root": cmd_root, "code-for": cmd_code_for}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        raise SystemExit(1)
    try:
        COMMANDS[sys.argv[1]](*sys.argv[2:])
    except RegistrationError as e:
        raise SystemExit(f"recusado: {e}")
