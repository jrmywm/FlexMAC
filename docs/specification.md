# Arithmetic and interface contract

## Product operation

Inputs a and b are 8-bit encodings. mode4=0 interprets each as one two's-complement
INT8 value and produces a signed 16-bit product. mode4=1 interprets the low and
high nibbles as two independent signed INT4 lanes, multiplies corresponding lanes,
and sums both products into one signed 16-bit output. The result is not two
separate accumulations. The INT4 pair sum ranges from -112 to +128, requiring
at least nine signed bits; it must not be truncated to eight.

For INT8, a byte equals 16 times its signed high nibble plus its unsigned low
nibble. The shared core reconstructs the product from four partial products.
The low-lane operands change to signed nibbles in INT4 mode; the two cross terms
are suppressed. Partial products are sign-extended before shifting. The mux
baseline contains separate INT8 and dual-INT4 units, making the cost of literal
duplication visible rather than calling it resource sharing.

## Framed accumulator

`flexmac_stream` has PRODUCT_IMPL=0 for the shared core or 1 for the mux baseline.
All handshakes are sampled on the rising edge. rst is synchronous active high;
handshake outputs and result payload are masked while rst is asserted.

1. start_valid && start_ready captures mode4, clears the accumulator, and starts a frame.
2. term_valid && term_ready accepts one packed operand pair. Only accepted beats
   update the accumulator. term_last marks the final accepted beat.
3. The result becomes valid just after the edge accepting the final beat. There
   is no extra output pipeline stage. It stays stable until result_ready is
   sampled high with result_valid.
4. A new command can be accepted on a later edge after result consumption returns
   the engine to IDLE. Commands and terms cannot be accepted in the same cycle.

The 32-bit signed accumulator wraps modulo 2^32. There is no saturation or
rounding inside this initial kernel. Invalid output payload is zero. An empty
frame is not supported. A frame may pause indefinitely between accepted terms.
Input operands have meaning only on accepted term beats; mode4 changes after
command acceptance do not change the active frame. Reset discards partial work
and any pending output.

One INT8 beat represents one scalar product; one INT4 beat represents two scalar
products in the same dot product. For an odd-length INT4 vector, the host must
zero-pad the unused second lane. Padding is not useful work. Steady-state RUN
can accept one beat per clock, but command, input stalls, result handling, and
operand delivery must be counted in end-to-end performance.

The first implementation is unpipelined between the input pins and accumulator.
It makes no clock-rate claim until constrained timing analysis is performed.
Operand isolation of cross terms is not a measured energy or power result.
