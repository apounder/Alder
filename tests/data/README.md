These are real calculation fixtures from the cclib project (BSD 3-clause;
see cclib-LICENSE.txt):

- gaussian-opt.log: https://github.com/cclib/cclib/blob/master/data/Gaussian/basicGaussian16/dvb_gopt.out
- orca-opt.out: https://github.com/cclib/cclib/blob/master/data/ORCA/basicORCA5.0/dvb_gopt.out
- orca6-opt.out: https://github.com/cclib/cclib/blob/master/data/ORCA/basicORCA6.0/dvb_gopt.out

They can also be opened in the application as examples.

Frequency fixtures (same cclib BSD license):

- gaussian-freq.log: https://github.com/cclib/cclib/blob/master/data/Gaussian/basicGaussian16/dvb_ir.out
- orca-freq.out: https://github.com/cclib/cclib/blob/master/data/ORCA/basicORCA5.0/dvb_ir.out

Both contain 20 atoms and 54 normal modes, with orbital energies, Cartesian mode
vectors, and IR intensities. These are real calculations, not invented spectra.

- gaussian-unrestricted.log: https://github.com/cclib/cclib/blob/master/data/Gaussian/basicGaussian16/dvb_un_sp.log (separate alpha/beta orbital levels)

Excited-state and additional job fixtures from cclib commit
[`f90be37ffa1ab4cfec97495bdd01d670ca329f17`](https://github.com/cclib/cclib/tree/f90be37ffa1ab4cfec97495bdd01d670ca329f17/data)
(same BSD license; files are unmodified):

| Local fixture | Upstream path |
| --- | --- |
| gaussian-td.log | `data/Gaussian/basicGaussian16/dvb_td.out` |
| gaussian-cis.log | `data/Gaussian/basicGaussian16/water_cis.log` |
| gaussian-eomccsd.log | `data/Gaussian/basicGaussian16/dvb_eomccsd.log` |
| orca-td.out | `data/ORCA/basicORCA5.0/dvb_td.out` |
| orca6-td.out | `data/ORCA/basicORCA6.0/dvb_td.out` |
| orca-adc2.out | `data/ORCA/basicORCA5.0/dvb_adc2.log` |
| orca6-adc2.out | `data/ORCA/basicORCA6.0/dvb_adc2.log` |
| orca-eomccsd.out | `data/ORCA/basicORCA5.0/dvb_eom_ccsd.log` |
| orca6-eomccsd.out | `data/ORCA/basicORCA6.0/dvb_eom_ccsd.log` |
| orca6-steom.out | `data/ORCA/basicORCA6.0/dvb_steom_dlpno_ccsd.log` |
| gaussian-mp2.log | `data/Gaussian/basicGaussian16/water_mp2.log` |
| orca6-mp2.out | `data/ORCA/basicORCA6.0/water_mp2.out` |
| gaussian-scan.log | `data/Gaussian/basicGaussian16/dvb_scan_unrelaxed.log` |
| orca6-scan.out | `data/ORCA/basicORCA6.0/dvb_scan_unrelaxed.out` |
| gaussian-cpcm.log | `data/Gaussian/basicGaussian16/water_hf_solvent_cpcm.log` |
| gaussian-smd.log | `data/Gaussian/basicGaussian16/water_hf_solvent_smd.log` |
| orca6-cpcm.log | `data/ORCA/basicORCA6.0/water_hf_solvent_cpcm.log` |
| orca6-smd.log | `data/ORCA/basicORCA6.0/water_hf_solvent_smd.log` |
| orca6-scan-relaxed.out | `data/ORCA/basicORCA6.0/dvb_scan_relaxed.out` |

Additional regression outputs from [cclib-data commit
`a16cc80ea29e8baec60abd0df346ce6862f52531`](https://github.com/cclib/cclib-data/tree/a16cc80ea29e8baec60abd0df346ce6862f52531)
(unmodified calculation outputs):

| Local fixture | Upstream path |
| --- | --- |
| gaussian-irc-path.out | `Gaussian/Gaussian09/ansaBPFP2_acetylene_ircf_LQA.out` |
| gaussian-scan2d.log | `Gaussian/Gaussian09/2D-PES-all-converged.log` |
| gaussian-eom-opt.log | `Gaussian/Gaussian16/Pyridine_opt-eomccsd.log` |
| orca-large-td.out | `ORCA/ORCA5.0/ADBNA_Me_Mes_MesCz.log` |
| orca-unrestricted.out | `ORCA/ORCA2.6/dvb_un_sp.out` |
