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
    check                                                     seed against the database

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
    return {k: node[k] for k in ("half_life_hours",) if k in node}


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


def cmd_check():
    """Report every difference between backend/data/attributes_tree.json and the
    database. No migration reads the live seed any more, so the seed says what a
    fresh install builds and this is what says whether it still does."""
    seed = _seed()
    tree = repos.load_attr_tree()
    templates = repos.load_action_templates()
    contributions = repos.load_all_contributions()
    diffs = []

    want_nodes = {n["key"]: n["name"] for n in seed["nodes"]}
    have_nodes = {k: n.name for k, n in tree.nodes_by_key.items()}
    for k in sorted(set(want_nodes) - set(have_nodes)):
        diffs.append(f"atributo só no seed: {k}")
    for k in sorted(set(have_nodes) - set(want_nodes)):
        diffs.append(f"atributo só no banco: {k}")
    for k in sorted(set(want_nodes) & set(have_nodes)):
        if want_nodes[k] != have_nodes[k]:
            diffs.append(f"{k}: nome '{have_nodes[k]}' no banco, '{want_nodes[k]}' no seed")

    want_edges = {(e["parent"], e["child"]): (float(e["weight"]), bool(e.get("primary", True)))
                  for e in seed["edges"]}
    have_edges = {(p, c): (w, prim)
                  for p, kids in tree.children.items() for c, w in kids
                  for prim in [any(pp == p and pr for pp, _w, pr in tree.parents.get(c, []))]}
    for e in sorted(set(want_edges) - set(have_edges)):
        diffs.append(f"ligação só no seed: {e[0]} -> {e[1]}")
    for e in sorted(set(have_edges) - set(want_edges)):
        diffs.append(f"ligação só no banco: {e[0]} -> {e[1]}")
    for e in sorted(set(want_edges) & set(have_edges)):
        (ws, ps), (wd, pd) = want_edges[e], have_edges[e]
        if abs(ws - wd) > 1e-9 or ps != pd:
            diffs.append(f"{e[0]} -> {e[1]}: {wd}{'' if pd else ' (não primária)'} no banco, "
                         f"{ws}{'' if ps else ' (não primária)'} no seed")

    want_contrib = {(c["action"].upper(), c["leaf"]): float(c["weight"]) for c in seed["contributions"]}
    have_contrib = {(a, leaf): w for a, leaves in contributions.items() for leaf, w in leaves}
    for c in sorted(set(want_contrib) - set(have_contrib)):
        diffs.append(f"contribuição só no seed: {c[0]} -> {c[1]}")
    for c in sorted(set(have_contrib) - set(want_contrib)):
        diffs.append(f"contribuição só no banco: {c[0]} -> {c[1]}")
    for c in sorted(set(want_contrib) & set(have_contrib)):
        if abs(want_contrib[c] - have_contrib[c]) > 1e-9:
            diffs.append(f"{c[0]} -> {c[1]}: {have_contrib[c]} no banco, {want_contrib[c]} no seed")

    fields = ("code", "parent", "type", "diff", "cost", "token_cost", "token_gain", "tiers", "log_only")
    want_t = {t["action"].upper(): t for t in seed["action_templates"]}
    for name in sorted(set(want_t) - set(templates)):
        diffs.append(f"ação só no seed: {name}")
    for name in sorted(set(templates) - set(want_t)):
        diffs.append(f"ação só no banco: {name}")
    for name in sorted(set(want_t) & set(templates)):
        for f in fields:
            a, b = want_t[name].get(f, False if f == "log_only" else None), templates[name].get(f)
            if f == "log_only":
                a, b = bool(a), bool(b)
            if a != b:
                diffs.append(f"{name}.{f}: {b!r} no banco, {a!r} no seed")

    for d in diffs:
        print(d)
    print(f"{len(diffs)} diferenças" if diffs else "seed e banco batem")
    raise SystemExit(1 if diffs else 0)


COMMANDS = {"show": cmd_show, "subdivide": cmd_subdivide, "add": cmd_add, "link": cmd_link,
            "reweight": cmd_reweight, "root": cmd_root, "code-for": cmd_code_for,
            "check": cmd_check}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        raise SystemExit(1)
    try:
        COMMANDS[sys.argv[1]](*sys.argv[2:])
    except RegistrationError as e:
        raise SystemExit(f"recusado: {e}")
