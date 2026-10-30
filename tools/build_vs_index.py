#!/usr/bin/env python3
"""
build_vs_index.py — parse the Vectorworks `vs.py` stub into a compact JSON
index of every function: arg names, arity, return type, category, one-line doc.

Purpose (bridge "knowledge index"): commands.py / execute_script can validate
argument counts BEFORE calling vs.* — turning VW engine errors (which pop a
modal "Script-Fehler" dialog) into clean Python-level error dicts, and giving
agents an instant, accurate signature lookup so scripts run right the first time.

Usage:
    python tools/build_vs_index.py <path-to-vs.py> [out.json]
Default output: vwx-plugin/vs_index.json  (deployed alongside commands.py).
"""
import ast, json, os, sys, re

def build(vs_path):
    src = open(vs_path, encoding='utf-8', errors='ignore').read()
    tree = ast.parse(src)
    index = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        args = [a.arg for a in node.args.args]
        n_required = len(args) - len(node.args.defaults)
        doc = ast.get_docstring(node) or ''
        category = ''
        ret = ''
        m = re.search(r'Category:\s*(.+)', doc)
        if m:
            category = m.group(1).strip()
        # return type hint from the trailing "return '<TYPE>'" in the stub
        rm = re.search(r"return\s*\(?\s*'([^']+)'", src[node.body[-1].lineno-1:node.end_lineno and 0 or 0:] if False else '')
        # simpler: scan the function's source slice
        fsrc = ast.get_source_segment(src, node) or ''
        rm = re.search(r"return\s*\(?\s*'([^']+)'", fsrc)
        if rm:
            ret = rm.group(1)
        # first meaningful doc line (skip the Python:/VectorScript: signature lines)
        summary = ''
        for line in doc.splitlines():
            s = line.strip()
            if s and not s.startswith(('Python:', 'VectorScript:', 'Category:')):
                summary = s
                break
        index[node.name] = {
            'args': args,
            'arity': len(args),
            'required': n_required,
            'ret': ret,
            'cat': category,
            'doc': summary[:200],
        }
    return index

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    vs_path = sys.argv[1]
    here = os.path.dirname(os.path.abspath(__file__))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, '..', 'vwx-plugin', 'vs_index.json')
    idx = build(vs_path)
    # Official current scripting reference includes plug-in functions absent
    # from the bundled SDK completion stub. Keep source URLs with the entries.
    with open(os.path.join(here, 'vs_supplement.json'), encoding='utf-8') as f:
        idx.update(json.load(f))
    # The SDK stub has stale part-index prose. Keep verified native behavior
    # when rebuilding so agents do not read empty data or write every accessory.
    for name in ('LDevice_GetParamStr', 'LDevice_GetParamLong'):
        if name in idx:
            idx[name]['doc'] = ('Read a typed Lighting Device/cell/accessory parameter. '
                'Use cellIndex>=0. accessoryIndex=-2 reads the parent cell; >=0 reads that accessory. '
                '-1 is unsupported for Get. Official Vectorworks/developer-scripting reference; verified VW2026.')
    for name in ('LDevice_SetParamStr', 'LDevice_SetParamLong'):
        if name in idx:
            idx[name]['doc'] = ('Write a typed Lighting Device/cell/accessory parameter. '
                'accessoryIndex=-2 targets the parent cell; >=0 targets that accessory; -1 writes ALL accessories. '
                'cellIndex=-1 writes ALL cells. Official Vectorworks/developer-scripting reference.')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False, separators=(',', ':'))
    cats = {}
    for v in idx.values():
        cats[v['cat']] = cats.get(v['cat'], 0) + 1
    print('indexed %d functions -> %s' % (len(idx), os.path.normpath(out)))
    print('top categories:')
    for c, n in sorted(cats.items(), key=lambda kv: -kv[1])[:12]:
        print('  %4d  %s' % (n, c or '(none)'))

if __name__ == '__main__':
    main()
