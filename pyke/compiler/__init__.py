# $Id$
# coding=utf-8
# 
# Copyright © 2007 Bruce Frederiksen
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from __future__ import with_statement
import contextlib
import os.path
import sys

# FIX: Take this out:
use_test = False

# If set, doesn't delete output files on error
# (if we don't want to nuke a hand tweaked compiler_bc.py).
no_nuke = False

import pyke

if use_test:
    from pyke.compiler import compiler_test_bc
else:
    from pyke.compiler import compiler_bc
from pyke.compiler import krbparser

#from pyke import contexts
#contexts.debug = ('patterns_out1', 'patterns_out',)

Ast_names = frozenset((
    'file',
    'parent',
    'fc_rule',
    'fc_predicate',
    'assert',
    'python_assertion',
    'python_eq',
    'python_in',
    'python_check',
    'counting',
    'bc_rule',
    'goal',
    'bc_predicate',
    'symbol',
    'pattern_var',
    'as',
    'plan_spec',
    'pattern_data',
    'pattern_tuple',
  # 'anonymous_var',
))

def dump(ast, f = sys.stderr, need_nl = False, indent = 0):
    if not isinstance(ast, tuple) or len(ast) == 0:
        f.write(repr(ast))
        return False
    if ast[0] in Ast_names:
        indent += 2
        if need_nl:
            f.write("\n")
            f.write(' ' * indent) 
        f.write('(%s' % ast[0])
        for arg in ast[1:]:
            f.write(', ')
            dump(arg, f, True, indent)
        f.write(')')
        return True
    f.write('(')
    did_nl = dump(ast[0], f, False, indent)
    for arg in ast[1:]:
        f.write(', ')
        did_nl |= dump(arg, f, did_nl, indent)
    f.write(')')
    return did_nl

def compile(gen_dir, gen_root_pkg, filenames):
    engine = pyke.engine(compiler_bc)
    for filename in filenames:
        compile_file(engine, gen_dir, gen_root_pkg, filename)

def compile_file(engine, gen_dir, gen_root_pkg, filename):
    rb_name = os.path.basename(filename)
    if not rb_name.endswith('.krb'):
        raise ValueError("compile: filename, %s, must end with .krb" % filename)
    rb_name = rb_name[:-4]
    if not pyke.Name_test.match(rb_name):
        raise ValueError("compile: %s illegal as python identifier" % rb_name)
    base_path, ignore = \
        pyke._get_base_path(filename, gen_dir, gen_root_pkg, True)
    fc_path = base_path + '_fc.py'
    bc_path = base_path + '_bc.py'
    plan_path = base_path + '_plans.py'
    try:
        ast = krbparser.parse(filename)
        #sys.stderr.write("got ast\n")
        # dump(ast)
        # sys.stderr.write('\n\n')
        engine.reset()
        if use_test:
            engine.activate('compiler_test')
            (fc_lines, bc_lines, plan_lines), plan = \
                engine.prove_1('compiler_test', 'compile', (rb_name, ast), 3)
        else:
            engine.activate('compiler')
            (fc_lines, bc_lines, plan_lines), plan = \
                engine.prove_1('compiler', 'compile', (rb_name, ast), 3)
        krb_filename = os.path.abspath(filename)
        if fc_lines:
            sys.stderr.write("writing %s\n" % fc_path)
            write_file(fc_lines + ("Krb_filename = '%s'" % krb_filename,),
                       fc_path)
        elif os.path.lexists(fc_path): os.remove(fc_path)
        if bc_lines:
            sys.stderr.write("writing %s\n" % bc_path)
            write_file(bc_lines + ("Krb_filename = '%s'" % krb_filename,),
                       bc_path)
        elif os.path.lexists(bc_path): os.remove(bc_path)
        if plan_lines:
            sys.stderr.write("writing %s\n" % plan_path)
            #sys.stderr.write("plan_lines:\n")
            #for line in plan_lines:
            #    sys.stderr.write("  " + repr(line) + "\n")
            write_file(plan_lines + ("Krb_filename = '%s'" % krb_filename,),
                       plan_path)
        elif os.path.lexists(plan_path): os.remove(plan_path)
        #sys.stderr.write("done!\n")
    except:
        if os.path.lexists(fc_path) and not no_nuke: os.remove(fc_path)
        if os.path.lexists(bc_path) and not no_nuke: os.remove(bc_path)
        if os.path.lexists(plan_path) and not no_nuke: os.remove(plan_path)
        raise

def write_file(lines, filename):
    with contextlib.closing(file(filename, 'w')) as f:
        indents = [0]
        lineno_map = []
        write_file2(lines, f, indents, lineno_map, 0)
        if lineno_map:
            f.write("Krb_lineno_map = (\n")
            for map_entry in lineno_map:
                f.write("    %s,\n" % str(map_entry))
            f.write(")\n")

def write_file2(lines, f, indents, lineno_map, lineno, starting_lineno = None):
    for line in lines:
        if line == 'POPINDENT':
            assert len(indents) > 1
            del indents[-1]
        elif isinstance(line, tuple):
            if len(line) == 2 and line[0] == 'INDENT':
                indents.append(indents[-1] + line[1])
            elif len(line) == 2 and line[0] == 'STARTING_LINENO':
                assert starting_lineno is None, \
                       "missing ENDING_LINENO for STARTING_LINENO %d" % \
                           starting_lineno[1]
                starting_lineno = line[1], lineno + 1
            elif len(line) == 2 and line[0] == 'ENDING_LINENO':
                assert starting_lineno is not None, \
                       "missing STARTING_LINENO for ENDING_LINENO %d" % \
                           line[1]
                lineno_map.append(((starting_lineno[1], lineno),
                                   (starting_lineno[0], line[1])))
                starting_lineno = None
            else:
                lineno, starting_lineno = \
                    write_file2(line, f, indents, lineno_map, lineno,
                                starting_lineno)
        else:
            f.write(' ' * indents[-1] + line + '\n')
            lineno += 1
    return lineno, starting_lineno


def test():
    import doctest
    sys.exit(doctest.testmod()[0])

if __name__ == "__main__":
    test()
