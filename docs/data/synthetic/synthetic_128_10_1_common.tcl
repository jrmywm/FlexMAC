read_liberty /home/runner/work/FlexMAC/FlexMAC/build/synthetic/map/library_pruned.lib
read_verilog /home/runner/work/FlexMAC/FlexMAC/build/synthetic/map/synthetic_128_10_1.v
link_design flexmac_mapped
read_sdc /home/runner/work/FlexMAC/FlexMAC/build/synthetic/map/synthetic_128_10_1_common.sdc
report_units
puts "CHECK_BEGIN"
check_setup -verbose
puts "CHECK_END"
set paths [find_timing_paths -from [all_registers -clock_pins] -to [all_registers -data_pins] -path_delay max -group_path_count 1]
foreach p $paths { puts "GROUP reg2reg [get_property $p slack] [get_full_name [get_property $p startpoint]] [get_full_name [get_property $p endpoint]]" }
set paths [find_timing_paths -from $data_inputs -to [all_registers -data_pins] -path_delay max -group_path_count 1]
foreach p $paths { puts "GROUP in2reg [get_property $p slack] [get_full_name [get_property $p startpoint]] [get_full_name [get_property $p endpoint]]" }
set paths [find_timing_paths -from [all_registers -clock_pins] -to [all_outputs] -path_delay max -group_path_count 1]
foreach p $paths { puts "GROUP reg2out [get_property $p slack] [get_full_name [get_property $p startpoint]] [get_full_name [get_property $p endpoint]]" }
set paths [find_timing_paths -from $data_inputs -to [all_outputs] -path_delay max -group_path_count 1]
foreach p $paths { puts "GROUP in2out [get_property $p slack] [get_full_name [get_property $p startpoint]] [get_full_name [get_property $p endpoint]]" }
report_worst_slack -max -digits 6
report_worst_slack -min -digits 6
puts "REPORT reg2reg"; report_checks -from [all_registers -clock_pins] -to [all_registers -data_pins] -path_delay max -group_path_count 1 -format full -digits 4
puts "REPORT in2reg"; report_checks -from $data_inputs -to [all_registers -data_pins] -path_delay max -group_path_count 1 -format full -digits 4
puts "REPORT reg2out"; report_checks -from [all_registers -clock_pins] -to [all_outputs] -path_delay max -group_path_count 1 -format full -digits 4
puts "REPORT in2out"; report_checks -from $data_inputs -to [all_outputs] -path_delay max -group_path_count 1 -format full -digits 4
puts "ELECTRICAL_BEGIN"
report_check_types -max_slew -max_capacitance -violators -digits 4
puts "ELECTRICAL_END"
