from digestify_api.exceptions.auth import InvalidCredentials
from digestify_api.exceptions.follows import (
    FollowLimitExceeded,
    UserAlreadyFollowsTopic,
    UserDoesNotFollowTopic,
)
from digestify_api.exceptions.topics import (
    TopicAlreadyExists,
    TopicContainsInappropriateContent,
    TopicLimitExceeded,
    TopicNotFound,
)
from digestify_api.exceptions.users import UserAlreadyExists, UserNotFound

__all__ = [
    "InvalidCredentials",
    "UserNotFound",
    "UserAlreadyExists",
    "TopicNotFound",
    "TopicAlreadyExists",
    "TopicLimitExceeded",
    "TopicContainsInappropriateContent",
    "FollowLimitExceeded",
    "UserAlreadyFollowsTopic",
    "UserDoesNotFollowTopic",
]
