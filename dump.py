import sys

import clang.cindex
from clang.cindex import Index
from clang.cindex import Config
from clang.cindex import TranslationUnit
from clang.cindex import CursorKind


class Visitor(object):
    def visit(self, cursor):
        cont = self.process(cursor)
        if cont:
            for child in cursor.get_children():
                self.visit(child)
            self.end(cursor)

    def process(self, cursor):
        return True

    def end(self, cursor):
        pass

class PrintVisitor(Visitor):
    def __init__(self):
        self.indent = 0

    def process(self, cursor):
        print("{}{}: {}".format(
            "  "*self.indent,
            cursor.kind.name,
            cursor.displayname))
        self.indent += 1
        return True

    def end(self, cursor):
        self.indent -= 1


def HeaderVisitor(Visitor):
    def process(self):
        return True


def dump_ast(cursor, decls, is_lib=False, lib="cu"):
    if "DECL" in cursor.kind.name:
        if cursor.displayname.startswith(lib):
            is_lib = True

    if is_lib:
        if cursor.kind == CursorKind.TYPEDEF_DECL:
            typedef_decl(cursor, decls)
            return
        elif cursor.kind == CursorKind.ENUM_DECL:
            enum_decl(cursor, decls)
            return
        elif cursor.kind == CursorKind.FUNCTION_DECL:
            function_decl(cursor, decls)
            return
    for child in cursor.get_children():
        dump_ast(child, decls, is_lib, lib)


def typedef_decl(cursor, decls=None):
    decl = cursor.spelling
    tgt = cursor.type.get_canonical().kind.spelling.lower()
    enumname = None
    for c in cursor.get_children():
        enumname = c.displayname
        break
    decls["typedef"].append([decl, tgt, enumname])
    # print("{}typedef {} {} {}".format(decls, tgt, decl))


def enum_decl(cursor, decls=None):
    decl = cursor.displayname
    tp = cursor.enum_type.get_canonical().kind.spelling.lower()
    # print("{}{} {}".format(decls, tp, decl))
    members = []
    for c in cursor.get_children():
        if c.kind == CursorKind.ENUM_CONSTANT_DECL:
            members.append([c.displayname, c.enum_value])
            # print("{}\t{} = {}".format(decls, c.displayname, c.enum_value))
    decls["enum"].append([decl, tp, members])


def function_decl(cursor, decls=None):
    decl = cursor.spelling
    body = cursor.displayname
    tp = None
    for c in cursor.get_children():
        tp = c.canonical.spelling
        break
    decls["function"].append([decl, tp, body])
    # print("{}{} {}".format(decls, tp, decl))


def make_typemap(decls):
    typemap = {}
    src = decls["typedef"]
    for decl, tp, enumname in src:
        if enumname is not None:
            typemap[decl] = enumname
        else:
            typemap[decl] = tp
    enums = decls["enum"]
    for decl, tp, _ in enums:
        typemap[decl] = tp

    return typemap


def make_enums(decls):
    src = decls["enum"]
    enums = []
    for _, _, members in src:
        for member in members:
            enums.append(member)
    return enums


def canonical_type(tp, typemap):
    while tp in typemap:
        tp = typemap[tp]
    return tp


def make_functions(decls, typemap):
    src = decls["function"]
    functions = []

    for decl, tp, body in src:
        tp = canonical_type(tp, typemap)
        functions.append([tp, body])

    return functions


def display(decls):
    for k in decls:
        for l in decls[k]:
            print(l)
        print()


def main():
    if len(sys.argv) < 3:
        print("usage: {} LIBNAME HEADER".format(sys.argv[0]))
        exit()
    header = sys.argv[2]
    lib = sys.argv[1]
    clang_args = [
        "-std=c++11",
        "-I./",
    ]
    index = Index.create()
    tu = index.parse(
        header,
        clang_args,
        None,
        TranslationUnit.PARSE_INCOMPLETE &
        TranslationUnit.PARSE_SKIP_FUNCTION_BODIES)

    enum_decls = []
    typedef_decls = []
    function_decls = []
    decls = {
        "enum": enum_decls,
        "function": function_decls,
        "typedef": typedef_decls,
    }
    dump_ast(tu.cursor, decls, lib=lib)
    # display(decls)
    typemap = make_typemap(decls)
    # print(typemap)
    enums = make_enums(decls)
    # print(enums)
    functions = make_functions(decls, typemap)
    # print(functions)

    print('cdef extern from *:')
    for tp in typemap:
        if typemap[tp] in typemap:
            print("    cptypedef {} {} '{}'".format(
                canonical_type(tp, typemap), tp.replace(lib, ""), tp))
        else:
            print("    cptypedef {} {} '{}'".format(
                typemap[tp], tp.replace(lib, ""), tp))
    print()
    print("cpdef enum:")
    for e in enums:
        print("    {} = {}".format(
            e[0].replace(lib.upper()+"_", ""), e[1]))
    print()
    for f in functions:
        body = f[1].replace(lib, "")
        body = body.replace(body[0], body[0].lower(), 1)
        print("cpdef {} {}".format(f[0], body))


if __name__ == '__main__':
    main()
