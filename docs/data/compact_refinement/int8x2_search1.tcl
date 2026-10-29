read_liberty /home/runner/work/FlexMAC/FlexMAC/build/compact_refinement/map/library_pruned.lib
read_verilog /home/runner/work/FlexMAC/FlexMAC/build/compact_refinement/map/int8x2.v
link_design flexmac_mapped
read_sdc /home/runner/work/FlexMAC/FlexMAC/build/compact_refinement/map/int8x2_search1.sdc
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
