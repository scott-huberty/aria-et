.. _task-pupillary-light-reflex:

Pupillary Light Reflex
======================

Preview
-------

.. vimeo:: 1214478086

`Pupillary Light Reflex video <https://vimeo.com/1214478086>`__

Description
-----------

The Pupillary Light Reflex task presents 18 trials. Each trial uses one of the
three PLR stimuli, ``plr65``, ``plr71``, or ``plr78``. Stimuli are presented from
pre-rendered image frames at 30 Hz with accompanying audio. The flash lasts four
frames, and the configured flash onset frame differs by stimulus:

.. list-table::
   :header-rows: 1
   :widths: 20 20

   * - Stimulus
     - Flash start frame
   * - ``plr65``
     - ``67``
   * - ``plr71``
     - ``73``
   * - ``plr78``
     - ``80``

Event Markers
-------------

The markers below are emitted as ``RuntimeEvent.name`` values by the Pupillary
Light Reflex presenter.

.. list-table::
   :header-rows: 1
   :widths: 40 30 30

   * - Marker
     - Meaning
     - Payload fields
   * - ``pupillary-light-reflex.started``
     - Task sequence began.
     - ``sequence_id``
   * - ``pupillary-light-reflex.trial.started``
     - A PLR trial began.
     - ``trial_id``, ``block_id``, ``block_number``, ``sequence_trial_number``, ``stimulus_id``, ``sound``, ``frame_count``, ``flash_frame_start``, ``flash_frame_count``
   * - ``pupillary-light-reflex.flash-frame.presented``
     - A flash frame was drawn and the window was flipped.
     - ``trial_id``, ``stimulus_id``, ``frame_index``, ``flash_frame_index``
   * - ``pupillary-light-reflex.trial.ended``
     - The trial completed.
     - ``trial_id``
   * - ``pupillary-light-reflex.ended``
     - Task sequence ended.
     - ``sequence_id``, ``trial_count``

Payload Field Reference
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 25 55 20

   * - Field
     - Description
     - Example or values
   * - ``sequence_id``
     - Task sequence identifier.
     - ``pupillary-light-reflex``
   * - ``trial_id``
     - Trial identifier assigned by sequence order.
     - ``plr-01`` through ``plr-18``
   * - ``block_id``
     - PLR block identifier. Each block contains one trial.
     - ``PLR-B01-O1`` through ``PLR-B18-O1``
   * - ``block_number``
     - One-based block number.
     - ``1`` through ``18``
   * - ``sequence_trial_number``
     - One-based trial number within the full PLR sequence.
     - ``1`` through ``18``
   * - ``stimulus_id``
     - PLR stimulus identity.
     - ``plr65``, ``plr71``, ``plr78``
   * - ``sound``
     - Bundled audio filename paired with the stimulus.
     - ``plr65.wav``, ``plr71.wav``, ``plr78.wav``
   * - ``frame_count``
     - Number of pre-rendered image frames in the stimulus.
     - Integer
   * - ``flash_frame_start``
     - One-based frame index for the first flash frame.
     - ``67``, ``73``, or ``80``
   * - ``flash_frame_count``
     - Number of consecutive flash frames.
     - ``4``
   * - ``frame_index``
     - One-based frame index for a presented flash frame.
     - Integer within the trial frame range
   * - ``flash_frame_index``
     - One-based index within the flash-frame sequence.
     - ``1`` through ``4``
   * - ``trial_count``
     - Number of trials completed before the task ended.
     - Integer from ``0`` to ``18``
