# Enums for defining frames and animations
from enum import Enum


class PetFrame(Enum):
    IDLE1 = 0
    IDLE2 = 1
    HAPPY = 2
    ANGRY = 3
    TRAIN1 = 4
    TRAIN2 = 5
    ATK1 = 6
    ATK2 = 7
    EAT1 = 8
    EAT2 = 9
    NOPE = 10
    #EXTRA = 11
    NAP1 = 11
    NAP2 = 12
    SICK = 13
    LOSE = 14
    SPECIAL = 15

class EggFrame(Enum):
    IDLE1, IDLE2, HATCH, DEAD = range(4)

class Animation:
    HATCH = [PetFrame.HAPPY]
    IDLE = [PetFrame.IDLE1, PetFrame.IDLE2]
    MOVING = [PetFrame.IDLE1, PetFrame.IDLE2]
    HAPPY = [PetFrame.HAPPY, PetFrame.IDLE1]
    HAPPY2 = [PetFrame.HAPPY, PetFrame.IDLE1]
    HAPPY3 = [PetFrame.HAPPY, PetFrame.IDLE1]
    NOPE = [PetFrame.NOPE, PetFrame.NOPE]
    ANGRY = [PetFrame.ANGRY, PetFrame.IDLE1]
    TRAIN = [PetFrame.TRAIN1, PetFrame.TRAIN2]
    ATTACK = [PetFrame.ATK1, PetFrame.ATK2]
    EAT = [PetFrame.EAT1, PetFrame.EAT2]
    NAP = [PetFrame.NAP1, PetFrame.NAP2]
    TIRED = [PetFrame.NAP1, PetFrame.NAP2]
    SICK = [PetFrame.SICK, PetFrame.ANGRY]
    POOPING = [PetFrame.SICK, PetFrame.SICK]
    LOSE = [PetFrame.LOSE, PetFrame.ANGRY]
    DYING = [PetFrame.LOSE, PetFrame.LOSE]
    SPECIAL = [PetFrame.SPECIAL, PetFrame.SPECIAL]