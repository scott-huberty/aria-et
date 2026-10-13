.. _task-calibration:

Child-Friendly Calibration
==========================

.. vimeo:: 1214478085

`Child-friendly calibration video <https://vimeo.com/1214478085>`__

Description
-----------

The child-friendly calibration is run by `DeToX
<https://pypi.org/project/dvst-detox/>`__ (``dvst-detox``), a PsychoPy and Tobii
SDK toolkit for infant-friendly eye tracking. aria-et resolves the tracker,
opens the PsychoPy window on the configured stimulus display, and hands the
calibration to DeToX:

1. **Positioning.** A screen shows the child's eye positions inside the
   tracker's track box and their distance from the screen. Press Space when the
   child is well positioned. Skip it with ``--skip-positioning``.
2. **Calibration.** Animated cartoon targets, with an attention-getting sound,
   appear at 5 points (corners and center) or 9 points. The operator presses a
   number key to show a target and Space to collect when the child is looking at
   it.
3. **Results.** Enter computes the calibration and shows the collected gaze
   against each target. The operator can redo individual points, restart, or
   accept. Escape aborts without saving.

An accepted calibration is applied on the tracker and saved under the session's
``calibrations/`` folder (``calibration.bin`` and ``calibration.json``, method
``child-friendly-detox``). Later runs record it as the calibration in effect.

Options
-------

.. list-table::
   :header-rows: 1
   :widths: 30 50 20

   * - Option
     - Effect
     - Default
   * - ``--points {5,9}``
     - Number of calibration targets.
     - ``5``
   * - ``--no-shuffle``
     - Present targets in a fixed order.
     - shuffled
   * - ``--animation {zoom,trill}``
     - Target animation.
     - ``zoom``
   * - ``--no-sound``
     - Turn off the attention-getting sound.
     - sound on
   * - ``--skip-positioning``
     - Skip the positioning screen.
     - shown

``aria-et demo-calibration`` previews the same procedure without a tracker,
using the mouse in place of gaze. Nothing is saved.
