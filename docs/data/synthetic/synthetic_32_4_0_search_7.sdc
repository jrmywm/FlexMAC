create_clock -name clk -period 13.046875 [get_ports clk]
set_clock_transition 0.1 [get_clocks clk]
set_clock_uncertainty -setup 0.1 [get_clocks clk]
set_clock_uncertainty -hold 0.0 [get_clocks clk]
set data_inputs [lsearch -all -inline -not -exact [all_inputs] [get_ports clk]]
set_input_delay -max 2.609375 -clock clk $data_inputs
set_input_delay -min 0.0 -clock clk $data_inputs
set_output_delay -max 2.609375 -clock clk [all_outputs]
set_output_delay -min 0.0 -clock clk [all_outputs]
set_driving_cell -lib_cell sky130_fd_sc_hd__buf_2 -pin X $data_inputs
set_load 0.01 [all_outputs]
