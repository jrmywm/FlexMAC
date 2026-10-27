"""Guard units, constraint diagnostics and failed-clock interpretation."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_mapping import prepare_library,parse_sta,sdc_text


class MappingTests(unittest.TestCase):
    def test_library_units_and_wire_pruning(self):
        text='''library ("example") {
time_unit : "1ns";
capacitive_load_unit(1.0000, "pf");
default_wire_load : "Small";
wire_load ("Small") { resistance : 1; }
cell ("sky130_fd_sc_hd__buf_2") { area : 3.5; pin ("X") { function : "A"; } }
cell ("sky130_fd_sc_hd__dfxtp_1") { area : 20; ff ("Q", "QN") { clocked_on : "CLK"; } }
cell ("sky130_fd_sc_hd__lpflow_test") { area : 100; }
}'''
        pruned,areas,sequential=prepare_library(text)
        self.assertNotIn('wire_load',pruned)
        self.assertNotIn('lpflow_test',pruned)
        self.assertEqual(areas['sky130_fd_sc_hd__dfxtp_1'],20)
        self.assertEqual(sequential,{'sky130_fd_sc_hd__dfxtp_1'})
        with self.assertRaises(ValueError): prepare_library(text.replace('"pf"','"ff"'))
        with self.assertRaises(ValueError): prepare_library(text.replace('"1ns"','"1ps"'))

    def test_failed_clock_is_not_a_passing_operating_point(self):
        text='CHECK_BEGIN\nCHECK_END\nGROUP reg2reg -2.5 a/Q b/D\nworst slack max -2.500000\nworst slack min 0.120000\n'
        metrics=parse_sta(text)
        self.assertFalse(metrics['setup_met']);self.assertTrue(metrics['hold_met'])
        self.assertEqual(parse_sta(text.replace('0.120000','1.2e-1'))['hold_wns_ns'],0.12)
        with self.assertRaises(ValueError): parse_sta(text.replace('CHECK_END','Warning: unconstrained endpoints\nCHECK_END'))
        with self.assertRaises(ValueError): parse_sta(text+'Error: failed linking\n')
        with self.assertRaises(ValueError): parse_sta(text+'Warning: unconstrained endpoints\n')
        with self.assertRaises(ValueError): parse_sta(text.replace('GROUP reg2reg -2.5 a/Q b/D','GROUP in2out -2.5 a b'))

    def test_sdc_matches_units_and_times_reset(self):
        import json
        root=Path(__file__).resolve().parents[1]
        cfg=json.loads((root/'eda/toolchain.json').read_text())
        sdc=sdc_text(10,cfg)
        self.assertIn('set_load 0.01 [all_outputs]',sdc)
        self.assertIn('set_input_delay -max 2.000000',sdc)
        self.assertIn('set_clock_transition 0.1 [get_clocks clk]',sdc)
        self.assertNotIn('set_false_path',sdc)
        self.assertEqual(cfg['output_load_ff'],1000*cfg['output_load_pf'])


if __name__=='__main__': unittest.main()
