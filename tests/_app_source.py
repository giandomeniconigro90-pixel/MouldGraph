# -*- coding: utf-8 -*-
"""Rebuild the app source as one AST, as the tests used to read it from the monolith.

The code now lives in the mouldgraph/ package: top-level definitions are spread over
several modules and LogAnalyzerApp is composed of mixins (mouldgraph/tabs/). The tests
execute selected pieces headlessly, so this helper merges them back into one module tree
with a single LogAnalyzerApp class containing every method.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
PKG = ROOT / 'mouldgraph'


def load_tree():
    body = []
    app_members = []
    for path in sorted(PKG.rglob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        is_tab = path.parent.name == 'tabs'
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and (is_tab or node.name == 'LogAnalyzerApp'):
                app_members.extend(node.body)
            elif not isinstance(node, (ast.Import, ast.ImportFrom)):
                body.append(node)
    app = ast.ClassDef(name='LogAnalyzerApp', bases=[], keywords=[], body=app_members,
                       decorator_list=[], type_params=[])
    body.append(app)
    return ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))


SOURCE = PKG
