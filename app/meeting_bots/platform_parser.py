from enum import Enum


class Platform(Enum):
    ZOOM = 1
    TEEMS = 2
    MEET = 3

    def __str__(self):
        return self.name

    @staticmethod
    def from_str(s: str):
        if s.lower() == "zoom":
            return Platform.ZOOM
        elif s.lower() == "teems":
            return Platform.TEEMS
        elif s.lower() == "meet":
            return Platform.MEET

        raise Exception("Unknown platform name")


def platform_by_url(url: str) -> Platform:
    if "zoom" in url:
        return Platform.ZOOM
    if "meet.google" in url:
        return Platform.MEET
    # TODO:
    # add other platforms

    return Platform.ZOOM
