from __future__ import annotations

from dataclasses import dataclass
import re

try:
    from tree_sitter import Language, Parser
    import tree_sitter_c_sharp
except Exception:  # pragma: no cover
    Language = Parser = None
    tree_sitter_c_sharp = None


@dataclass(slots=True)
class ParseResult:
    symbols: list[dict]
    references: list[dict]


TYPE_NODES = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "struct_declaration": "struct",
    "record_declaration": "record",
    "enum_declaration": "enum",
}
MEMBER_NODES = {
    "method_declaration": "method",
    "constructor_declaration": "constructor",
    "property_declaration": "property",
}


class CSharpParser:
    def __init__(self):
        self.parser = None
        if Parser is not None and tree_sitter_c_sharp is not None:
            try:
                language = Language(tree_sitter_c_sharp.language())
                self.parser = Parser(language)
            except Exception:
                self.parser = None

    @staticmethod
    def _text(source: bytes, node) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def parse(self, text: str) -> ParseResult:
        if self.parser is None:
            return self._fallback(text)
        source = text.encode("utf-8")
        tree = self.parser.parse(source)
        symbols: list[dict] = []
        refs: list[dict] = []

        def namespace_for(node) -> str:
            parts: list[str] = []
            cur = node.parent
            while cur:
                if cur.type in {"namespace_declaration", "file_scoped_namespace_declaration"}:
                    name = cur.child_by_field_name("name")
                    if name:
                        parts.append(self._text(source, name))
                cur = cur.parent
            return ".".join(reversed(parts))

        def containing_types(node) -> list[str]:
            names: list[str] = []
            cur = node.parent
            while cur:
                if cur.type in TYPE_NODES:
                    name = cur.child_by_field_name("name")
                    if name:
                        names.append(self._text(source, name))
                cur = cur.parent
            return list(reversed(names))

        def signature(node) -> str:
            raw = self._text(source, node)
            brace = raw.find("{")
            arrow = raw.find("=>")
            semi = raw.find(";")
            cuts = [x for x in (brace, arrow, semi) if x >= 0]
            return raw[: min(cuts)] if cuts else raw[:500]

        def visit(node, current_symbol_key=None):
            symbol_key = current_symbol_key
            kind = TYPE_NODES.get(node.type) or MEMBER_NODES.get(node.type)
            if kind:
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._text(source, name_node)
                    ns = namespace_for(node)
                    parents = containing_types(node)
                    full_parts = ([ns] if ns else []) + parents + [name]
                    full_name = ".".join(full_parts)
                    item = {
                        "kind": kind,
                        "namespace": ns,
                        "name": name,
                        "full_name": full_name,
                        "signature": signature(node).strip(),
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                        "content": self._text(source, node),
                    }
                    symbols.append(item)
                    symbol_key = (full_name, item["start_line"])
            if node.type == "identifier":
                ident = self._text(source, node)
                if ident and ident[0].isupper():
                    refs.append({
                        "source_symbol_key": symbol_key,
                        "target_name": ident,
                        "reference_type": "identifier",
                        "line": node.start_point[0] + 1,
                    })
            for child in node.children:
                visit(child, symbol_key)

        visit(tree.root_node)
        return ParseResult(symbols=symbols, references=refs)

    def _fallback(self, text: str) -> ParseResult:
        namespace = ""
        ns_match = re.search(r"\bnamespace\s+([A-Za-z_][\w.]*)", text)
        if ns_match:
            namespace = ns_match.group(1)
        symbols: list[dict] = []
        lines = text.splitlines()
        type_rx = re.compile(r"\b(class|interface|struct|record|enum)\s+([A-Za-z_]\w*)")
        method_rx = re.compile(r"(?:public|private|protected|internal|static|virtual|override|async|sealed|new|partial|extern|unsafe|\s)+[\w<>,?\[\].]+\s+([A-Za-z_]\w*)\s*\(")
        current_type = None
        for i, line in enumerate(lines, 1):
            tm = type_rx.search(line)
            if tm:
                current_type = tm.group(2)
                full = f"{namespace}.{current_type}" if namespace else current_type
                symbols.append({"kind": tm.group(1), "namespace": namespace, "name": current_type, "full_name": full, "signature": line.strip(), "start_line": i, "end_line": i, "content": line})
            if current_type:
                # Fallback mode intentionally prefers recall over perfect parsing; tree-sitter
                # is used when available. finditer also catches compact/minified test fixtures.
                for mm in method_rx.finditer(line):
                    name = mm.group(1)
                    if name == current_type:
                        continue
                    full = ".".join(x for x in (namespace, current_type, name) if x)
                    if not any(s["full_name"] == full and s["start_line"] == i for s in symbols):
                        symbols.append({"kind": "method", "namespace": namespace, "name": name, "full_name": full, "signature": mm.group(0).strip(), "start_line": i, "end_line": i, "content": line})
        refs = []
        for i, line in enumerate(lines, 1):
            for ident in re.findall(r"\b[A-Z][A-Za-z0-9_]*\b", line):
                refs.append({"source_symbol_key": None, "target_name": ident, "reference_type": "identifier", "line": i})
        return ParseResult(symbols=symbols, references=refs)
