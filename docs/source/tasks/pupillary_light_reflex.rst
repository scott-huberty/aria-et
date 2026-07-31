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
