#!/usr/bin/env python3

import datetime
from enum import Enum
import math

class CallParseError(Exception):
    pass

class Direction(Enum):
    INCOMING = 'INCOMING'
    OUTGOING = 'OUTGOING'

class PhoneNumber:
    cost_per_minute = None
    connection_charge = None

    def __init__(self, number):
        if self.cost_per_minute is None or self.connection_charge is None:
            raise NotImplementedError('Cannot instantiate generic PhoneNumber')
        self.number = number

    @classmethod
    def from_string(cls, number):
        #
        # Standardise country code syntax by replacing '+' with '00'
        number = number.replace('+', '00')
        #
        # If number starts with '0044', replace that part with '0' because
        # it is not international
        if number.startswith('0044'):
            number = '0' + number[4:]
        #
        # Number is international if it starts with 00
        if number[0,1] == '00':
            return InternationalNumber(number)
        #
        # Landline numbers start with 01 or 02
        if number[0,1] in ['01', '02']:
            return LandlineNumber(number)
        #
        # Freephone numbers start with 080
        if number [0,2] == '080':
            return FreeNumber(number)
        #
        # Mobile numbers start with 07
        if number[0,1] == '07':
            #
            # Unless it is 076 and not 07624
            if number[2] != '6' or number[3:5] != '24':
                return MobileNumber(number)
        #
        # Everything else is invalid
        return InvalidNumber(number)


class InternationalNumber(PhoneNumber):
    cost_per_minute = 80
    connection_charge = 50

class LandlineNumber(PhoneNumber):
    cost_per_minute = 15
    connection_charge = 0

class MobileNumber(PhoneNumber):
    cost_per_minute = 30
    connection_charge = 0

class FreeNumber(PhoneNumber):
    cost_per_minute = 0
    connection_charge = 0

class InvalidNumber(PhoneNumber):
    cost_per_minute = 0
    connection_charge = 0

class PhoneCall:
    def __init__(self, number, start_time, duration, direction):
        #
        # Phone number class will depend on its first characters
        self.number = PhoneNumber.from_string(number)
        #
        # Start time is in ISO 8601 format but may end with 'Z' instead of
        # the +00:00 expected by datetime
        try:
            self.start_time = datetime.datetime.fromisoformat(
                start_time.replace('Z','+00:00')
            )
        except:
            raise CallParseError(f'Error parsing start time {start_time}')
        #
        # Duration is in the format 'MM:SS'. We need the number of started minutes
        try:
            minutes, seconds = duration.split(':')
            if seconds:
                minutes += 1
            self.duration = minutes
        except:
            raise CallParseError(f'Error parsing duration {duration}')
        #
        # Direction should be either INCOMING or OUTGOING
        self.direction = Direction(direction)

    def call_cost(self):
        if self.direction == Direction.INCOMING:
            return 0
        #
        # Charge is per started minute with an additional connection charge
        cost = self.number.connection_charge + \
            (self.duration * self.number.cost_per_minute)

        return cost