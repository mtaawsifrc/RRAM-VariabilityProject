* Stanford RRAM bipolar butterfly I-V curve

.OPTION POST=2
.OPTION RUNLVL=5

.hdl rram_v_1_0_0_hspice.va

* Start from HRS
X1 in 0 rram_v_1_0_0 gap_ini=17e-10 model_switch=0 deltaGap0=1e-4 g0=1e-9

* 0 -> +2V -> 0 -> -2V -> 0
Vin in 0 PWL(0 0 1m 2 2m 0 3m -2 4m 0)
* Vin in 0 PWL(0 0 2m 3 4m 0 6m -3 8m 0)
* .tran 1u 8m
.tran 1u 4m

.probe V(in) I(Vin)
.print tran V(in) I(Vin)

.end
