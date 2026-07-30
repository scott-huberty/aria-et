from aria_et.psychopy.environment import (
    configure_audio,
    configure_monitor,
    demo_movie_factory,
    demo_sound_factory,
    effective_window_size,
    open_window,
)


class FakeMonitor:
    def __init__(self, name, width=None, distance=None):
        self.name = name
        self.width = width
        self.distance = distance
        self.size_pix = None
        self.saved = False

    def setSizePix(self, size_pix):
        self.size_pix = size_pix

    def saveMon(self):
        self.saved = True


class FakeMonitors:
    def __init__(self):
        self.created = []

    def Monitor(self, name, width=None, distance=None):
        monitor = FakeMonitor(name, width=width, distance=distance)
        self.created.append(monitor)
        return monitor


class FakeVisual:
    def __init__(self):
        self.window_kwargs = None

    def Window(self, **kwargs):
        self.window_kwargs = kwargs
        return kwargs


class FakePrefs:
    def __init__(self):
        self.hardware = {}


class FakeSpeakerError(BaseException):
    pass


def test_effective_window_size_uses_screen_resolution_for_fullscreen():
    assert effective_window_size(
        fullscreen=True,
        window_size=(1024, 768),
        screen_resolution_pixels=(1920, 1080),
    ) == (1920, 1080)
    assert effective_window_size(
        fullscreen=False,
        window_size=(1024, 768),
        screen_resolution_pixels=(1920, 1080),
    ) == (1024, 768)


def test_configure_monitor_creates_saved_psychopy_monitor_profile():
    monitors = FakeMonitors()

    monitor = configure_monitor(
        monitors_module=monitors,
        monitor_name="EIZO_EV2480",
        screen_distance_meters=0.65,
        screen_resolution_pixels=(1920, 1080),
        screen_size_meters=(0.527, 0.296),
    )

    assert monitor.name == "EIZO_EV2480"
    assert monitor.width == 52.7
    assert monitor.distance == 65.0
    assert monitor.size_pix == (1920, 1080)
    assert monitor.saved is True


def test_configure_audio_sets_psychopy_default_speaker():
    prefs = FakePrefs()

    configure_audio(prefs_module=prefs, audio_speaker="EV2480")

    assert prefs.hardware["audioDevice"] == ["EV2480"]


def test_open_window_uses_monitor_audio_and_effective_fullscreen_size():
    visual = FakeVisual()
    monitors = FakeMonitors()
    prefs = FakePrefs()

    window = open_window(
        visual_module=visual,
        monitors_module=monitors,
        prefs_module=prefs,
        fullscreen=True,
        screen=1,
        window_size=(1024, 768),
        screen_distance_meters=0.65,
        screen_resolution_pixels=(1920, 1080),
        screen_size_meters=(0.527, 0.296),
        monitor_name="EIZO_EV2480",
        audio_speaker="EV2480",
    )

    assert prefs.hardware["audioDevice"] == ["EV2480"]
    assert window["size"] == (1920, 1080)
    assert window["fullscr"] is True
    assert window["screen"] == 1
    assert window["monitor"].name == "EIZO_EV2480"


def test_demo_sound_factory_falls_back_to_default_speaker():
    prefs = FakePrefs()
    prefs.hardware["audioDevice"] = ["EV2480"]
    statuses = []
    calls = []

    class FakeSoundModule:
        @staticmethod
        def Sound(path):
            calls.append((path, tuple(prefs.hardware["audioDevice"])))
            if len(calls) == 1:
                raise FakeSpeakerError("No speaker device found with name 'EV2480'")
            return {"path": path}

    make_sound = demo_sound_factory(
        sound_module=FakeSoundModule,
        prefs_module=prefs,
        status_sink=statuses.append,
    )

    assert make_sound("reward.wav") == {"path": "reward.wav"}
    assert calls == [
        ("reward.wav", ("EV2480",)),
        ("reward.wav", ("default",)),
    ]
    assert prefs.hardware["audioDevice"] == ["default"]
    assert "trying PsychoPy's default speaker" in statuses[0]


def test_demo_sound_factory_reraises_if_default_speaker_also_fails():
    prefs = FakePrefs()
    prefs.hardware["audioDevice"] = ["EV2480"]

    class FakeSoundModule:
        @staticmethod
        def Sound(path):
            raise FakeSpeakerError("No available speaker")

    make_sound = demo_sound_factory(
        sound_module=FakeSoundModule,
        prefs_module=prefs,
        status_sink=lambda message: None,
    )

    try:
        make_sound("reward.wav")
    except FakeSpeakerError as error:
        assert "No available speaker" in str(error)
    else:
        raise AssertionError("Expected fallback speaker failure to be re-raised.")


def test_demo_movie_factory_falls_back_to_default_speaker():
    prefs = FakePrefs()
    prefs.hardware["audioDevice"] = ["EV2480"]
    statuses = []
    calls = []

    class FakeVisualModule:
        @staticmethod
        def MovieStim(window, **kwargs):
            calls.append((window, kwargs, tuple(prefs.hardware["audioDevice"])))
            if len(calls) == 1:
                raise FakeSpeakerError("No speaker device found with name 'EV2480'")
            return {"movie": kwargs}

    make_movie = demo_movie_factory(
        visual_module=FakeVisualModule,
        prefs_module=prefs,
        status_sink=statuses.append,
        play_sound=True,
        audio_speaker="EV2480",
    )

    assert make_movie("window", "movie.mp4") == {
        "movie": {
            "filename": "movie.mp4",
            "noAudio": False,
            "audioDevice": None,
        }
    }
    assert calls[0][1] == {
        "filename": "movie.mp4",
        "noAudio": False,
        "audioDevice": "EV2480",
    }
    assert calls[1][2] == ("default",)
    assert prefs.hardware["audioDevice"] == ["default"]
    assert "trying PsychoPy's default speaker" in statuses[0]


def test_demo_movie_factory_falls_back_to_silent_movie_if_default_speaker_fails():
    prefs = FakePrefs()
    prefs.hardware["audioDevice"] = ["EV2480"]
    statuses = []
    calls = []

    class FakeVisualModule:
        @staticmethod
        def MovieStim(window, **kwargs):
            calls.append(kwargs)
            if kwargs["noAudio"]:
                return {"movie": kwargs}
            raise FakeSpeakerError("No available speaker")

    make_movie = demo_movie_factory(
        visual_module=FakeVisualModule,
        prefs_module=prefs,
        status_sink=statuses.append,
        play_sound=True,
        audio_speaker="EV2480",
    )

    assert make_movie("window", "movie.mp4") == {
        "movie": {
            "filename": "movie.mp4",
            "noAudio": True,
        }
    }
    assert calls == [
        {
            "filename": "movie.mp4",
            "noAudio": False,
            "audioDevice": "EV2480",
        },
        {
            "filename": "movie.mp4",
            "noAudio": False,
            "audioDevice": None,
        },
        {
            "filename": "movie.mp4",
            "noAudio": True,
        },
    ]
    assert "trying PsychoPy's default speaker" in statuses[0]
    assert "Sound playback is disabled for this demo" in statuses[1]
