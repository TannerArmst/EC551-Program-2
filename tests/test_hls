"""Compiler invariants and independent sequential-versus-scheduled execution."""
import json
from pathlib import Path
import random
import tempfile
import unittest
import hls

CAPS = dict(add=1,sub=1,mul=1)
class CompilerTests(unittest.TestCase):
    def test_ssa_reassignment_and_self_read(self):
        p=hls.parse('X=X+A\nX=X*X\nA=X-A')
        self.assertEqual(p.ssa(),'X_1 = X_0 + A_0\nX_2 = X_1 * X_1\nA_1 = X_2 - A_0\n')
        self.assertEqual(p.nodes[1].deps,(0,))
        self.assertEqual(p.nodes[2].deps,(1,))
        self.assertEqual(p.outputs,{'X':'X_2','A':'A_1'})
        self.assertEqual(hls.evaluate(p,{'X':2,'A':3})['A_1'],22)

    def test_external_first_read_is_not_forward_dependency(self):
        p=hls.parse('Y=X+A\nX=B+C')
        self.assertEqual(p.input_names,['X','A','B','C'])
        self.assertEqual(p.nodes[0].a,'X_0')
        self.assertEqual(p.nodes[0].deps,())

    def test_parser_grammar_and_errors(self):
        p=hls.parse('# header\nX = A+0x10; // comment\n\nY=X-2')
        self.assertEqual(p.nodes[0].b,16)
        for text in ('','X=A/B','X=A+B+C','X=-A+B','X=A','X=(A+B)*C','X=A+1\nbad'):
            with self.subTest(text=text), self.assertRaises(hls.HLSError): hls.parse(text)
        self.assertEqual(len(hls.parse('\n'.join(f'X=X+{i}' for i in range(20))).nodes),20)
        with self.assertRaises(hls.HLSError): hls.parse('\n'.join(f'X=X+{i}' for i in range(21)))

    def test_exact_schedules(self):
        p=hls.parse('X=A+B\nY=X+A\nZ=X-B\nQ=B*Z')
        t,l,_=hls.schedule(p,'asap')
        self.assertEqual(t,{0:1,1:2,2:2,3:3})
        self.assertEqual(l,3)
        t,l,_=hls.schedule(p,'alap',latency=5)
        self.assertEqual(t,{0:3,1:5,2:4,3:5})
        self.assertEqual(l,5)
        p=hls.parse('X=A+B\nY=A+B\nZ=X+Y')
        t,l,c=hls.schedule(p,'constrained-asap',CAPS)
        self.assertEqual(t,{0:1,1:2,2:3})
        self.assertEqual(hls.bind(p,t)[1],{'add':1,'sub':0,'mul':0})
        t,l,c=hls.schedule(p,'asap',CAPS)
        self.assertEqual(hls.bind(p,t)[1],{'add':2,'sub':0,'mul':0})
        self.assertEqual(l,2)

    def test_custom_prioritizes_critical_path(self):
        p=hls.parse('unused=A+B\nX=A+B\nY=X*B\nZ=Y*A')
        _,lf,_=hls.schedule(p,'constrained-asap',CAPS)
        _,lc,_=hls.schedule(p,'custom',CAPS)
        self.assertEqual((lf,lc),(4,3))

    def test_bound_and_disabled_resource_failures(self):
        p=hls.parse('X=A+B\nY=A+B\nZ=X+Y')
        for mode in hls.MODES:
            with self.assertRaises(hls.HLSError): hls.schedule(p,mode,CAPS,1)
        with self.assertRaises(hls.HLSError): hls.schedule(p,'constrained-asap',CAPS,2)
        with self.assertRaises(hls.HLSError): hls.schedule(p,'constrained-alap',CAPS,2)
        with self.assertRaises(hls.HLSError): hls.schedule(p,'custom',{'add':0})
        for bound in (0,-1,4096):
            with self.assertRaises(hls.HLSError): hls.schedule(p,latency=bound)
        with self.assertRaises(hls.HLSError): hls.schedule(p,'unknown')
        with self.assertRaises(hls.HLSError): hls.validate(p,{0:1,1:1,2:1},CAPS)

    def test_unsigned_boundaries(self):
        p=hls.parse('X=A+B\nY=A-B\nZ=A*B')
        env=hls.evaluate(p,{'A':15,'B':2},4)
        self.assertEqual([env[n.dst] for n in p.nodes],[1,13,14])
        self.assertEqual(hls.evaluate(p,{'A':0,'B':1},4)['Y_1'],15)

    def test_generated_mapping_and_input_validation(self):
        p=hls.parse('X=A+B\nX=X*C')
        t,l,c=hls.schedule(p)
        with tempfile.TemporaryDirectory() as d:
            m=hls.emit(p,t,l,c,'constrained-asap',16,d,{'C':2},['B','A'],vectors=1)
            self.assertEqual(m['outputs'],{'X':'X_2'})
            self.assertEqual(m['board_switch_inputs'],['B','A'])
            self.assertEqual(m['board_static_inputs'],{'C':2})
            self.assertTrue((Path(d)/'testbench.v').exists())
            for kwargs in ({'constants':{'unknown':1}}, {'constants':{'A':65536}},
                           {'switch_inputs':['A','A']}, {'switch_inputs':['A','B','C']},
                           {'constants':{'A':1},'switch_inputs':['A']}, {'vectors':0}):
                with self.subTest(kwargs=kwargs),self.assertRaises(hls.HLSError):
                    hls.emit(p,t,l,c,'constrained-asap',16,d,**kwargs)

    def test_random_programs_independent_execution(self):
        rng=random.Random(551)
        for trial in range(120):
            # Direct source-language execution keeps original names, not SSA.
            values={x:rng.randrange(256) for x in ['A','B','C','D','X','Y','Z']}
            available=['A','B','C','D']
            lines=[]
            expected=dict(values)
            for i in range(rng.randrange(1,21)):
                dst=rng.choice(['X','Y','Z'])
                a,b=rng.choice(available),rng.choice(available)
                op=rng.choice('+-*')
                lines.append(f'{dst}={a}{op}{b}')
                if op=='+': v=expected[a]+expected[b]
                elif op=='-': v=expected[a]-expected[b]
                else: v=expected[a]*expected[b]
                expected[dst]=v&255
                if dst not in available: available.append(dst)
            p=hls.parse('\n'.join(lines))
            caps={k:rng.randrange(1,4) for k in CAPS}
            for mode in hls.MODES:
                with self.subTest(trial=trial,mode=mode):
                    t,l,c=hls.schedule(p,mode,caps)
                    hls.validate(p,t,c)
                    binding,peaks=hls.bind(p,t)
                    env={s:values[name] for name,s in zip(p.input_names,p.inputs)}
                    for cycle in range(1,l+1):
                        updates={}
                        occupied=set()
                        for n in p.nodes:
                            if t[n.id]!=cycle: continue
                            self.assertNotIn(binding[n.id],occupied)
                            occupied.add(binding[n.id])
                            a,b=(x if isinstance(x,int) else env[x] for x in (n.a,n.b))
                            v=a+b if n.op=='+' else a-b if n.op=='-' else a*b
                            updates[n.dst]=v&255
                        env.update(updates)
                    for name,s in p.outputs.items(): self.assertEqual(env[s],expected[name])
                    if mode not in ('asap','alap'):
                        for k,v in peaks.items(): self.assertLessEqual(v,caps[k])

if __name__=='__main__': unittest.main()
