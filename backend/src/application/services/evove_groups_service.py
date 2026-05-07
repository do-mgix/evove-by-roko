import os
import re

GROUPS_FILE = "/home/mgix/journal/evove-groups"


def parse_groups(path=None):
    """Returns {parent_name_upper: [(value, child_name_upper), ...]}"""
    path = path or GROUPS_FILE
    result = {}
    if not os.path.isfile(path):
        return result

    current_parent = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    current_parent = None
                    continue
                m = re.match(r'^(\d+)\s*[xX]\s*(.+)$', line)
                if m and current_parent is not None:
                    result.setdefault(current_parent, []).append(
                        (int(m.group(1)), m.group(2).strip().upper())
                    )
                elif not m:
                    current_parent = line.upper()
                    result.setdefault(current_parent, [])
    except OSError:
        pass
    return result


def get_group_children(action_name):
    """Returns [(value, child_name_upper), ...] for a given parent action name."""
    return parse_groups().get(str(action_name).upper(), [])
