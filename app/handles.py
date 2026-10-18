"""Neutral nickname generator. Users pick from generated handles, never type one."""

import re
import secrets

_ADJECTIVE_WORDS = """
    amber brave bright calm clever cosy crisp curious dapper eager fluffy gentle golden
    happy hazel honest humble jolly kind lively lucky mellow merry misty nimble noble
    patient plucky polite proud quick quiet rapid rosy rusty shiny silent silver sleepy
    smooth snowy sober steady sunny swift tidy velvet vivid warm witty
"""
_NOUN_WORDS = """
    badger beaver bison comet crane dolphin falcon ferret finch fox gecko hare hedgehog
    heron ibis koala lark lemur lynx magpie marten meadow mole moose newt orca otter owl
    panda pebble pelican pine puffin quail raven river robin seal sparrow squirrel stork
    swan thistle tiger turtle walrus willow wolf wren yak
"""
ADJECTIVES = tuple(_ADJECTIVE_WORDS.split())
NOUNS = tuple(_NOUN_WORDS.split())
NUMBER_MIN = 10
NUMBER_MAX = 99

_HANDLE_RE = re.compile(r"([a-z]+)-([a-z]+)-(\d{2})")


def generate_handle() -> str:
    number = NUMBER_MIN + secrets.randbelow(NUMBER_MAX - NUMBER_MIN + 1)
    return f"{secrets.choice(ADJECTIVES)}-{secrets.choice(NOUNS)}-{number}"


def is_generated_handle(value: str) -> bool:
    match = _HANDLE_RE.fullmatch(value)
    if match is None:
        return False
    adjective, noun, number = match.groups()
    return adjective in ADJECTIVES and noun in NOUNS and NUMBER_MIN <= int(number) <= NUMBER_MAX
