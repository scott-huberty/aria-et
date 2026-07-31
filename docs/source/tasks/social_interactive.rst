.. _task-social-interactive:

Social Interactive
==================

Preview
-------

.. vimeo:: 1214478083

`Social Interactive video <https://vimeo.com/1214478083>`__

Description
-----------

Social Interactive presents 22 video trials across four blocks. The task
includes 11 parallel-play trials and 11 cooperative-play trials. Each video is
presented for 15 seconds after a one-second fixation interval, followed by a
0.25-second blank interval.

Event Markers
-------------

The markers below are emitted as ``RuntimeEvent.name`` values by the Social
Interactive presenter.

.. list-table::
   :header-rows: 1
   :widths: 35 35 30

   * - Marker
     - Meaning
     - Payload fields
   * - ``social-interactive.started``
     - Task sequence began.
     - ``sequence_id``
   * - ``social-interactive.trial.started``
     - A trial began, before fixation and video presentation.
     - ``trial_id``, ``block_id``, ``block_number``, ``block_trial_number``, ``sequence_trial_number``, ``source_id``, ``play_condition``, ``video``
   * - ``social-interactive.trial.ended``
     - The trial completed.
     - ``trial_id``
   * - ``social-interactive.ended``
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
     - ``social-interactive``
   * - ``trial_id``
     - Trial identifier assigned by sequence order.
     - ``si-01`` through ``si-22``
   * - ``block_id``
     - Social Interactive block identifier.
     - ``SI-B1`` through ``SI-B4``
   * - ``block_number``
     - One-based block number.
     - ``1`` through ``4``
   * - ``block_trial_number``
     - One-based trial number within the current block.
     - ``1`` through ``6``
   * - ``sequence_trial_number``
     - One-based trial number within the full task sequence.
     - ``1`` through ``22``
   * - ``source_id``
     - Source stimulus identity from the task sequence definition.
     - Two-digit string, for example ``01`` or ``12``
   * - ``play_condition``
     - Social play condition represented by the video.
     - ``parallel-play`` or ``cooperative-play``
   * - ``video``
     - Bundled video filename presented on that trial.
     - ``sibs*_non_15s.mp4`` or ``sibs*_soc_15s.mp4``
   * - ``trial_count``
     - Number of trials completed before the task ended.
     - Integer from ``0`` to ``22``
