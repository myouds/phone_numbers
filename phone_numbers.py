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
        if number[0:2] == '00':
            return InternationalNumber(number)
        #
        # Landline numbers start with 01 or 02
        if number[0:2] in ['01', '02']:
            return LandlineNumber(number)
        #
        # Freephone numbers start with 080
        if number [0:3] == '080':
            return FreeNumber(number)
        #
        # Mobile numbers start with 07
        if number[0:2] == '07':
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
        except Exception as e:
            raise CallParseError(
                f'Error parsing start time {start_time}'
            ) from e
        #
        # Duration is in the format 'MM:SS'. We need the number of started minutes
        try:
            minutes, seconds = duration.split(':')
            minutes = int(minutes)
            seconds = int(seconds)
            if seconds:
                minutes += 1
            self.duration = minutes
        except Exception as e:
            raise CallParseError(
                f'Error parsing duration {duration}'
            ) from e
        #
        # Direction should be either INCOMING or OUTGOING
        self.direction = Direction(direction)

    def cost(self):
        if self.direction == Direction.INCOMING:
            return 0
        #
        # Charge is per started minute with an additional connection charge
        cost = self.number.connection_charge + \
            (self.duration * self.number.cost_per_minute)

        return cost

    @classmethod
    def from_csv(cls, csv_line):
        #
        # CSV line should be in the format:
        # PhoneNumber,CallStartTime,CallDuration,CallDirection
        try:
            num, start, duration, direction = csv_line.split(',')
        except Exception as e:
            raise CallParseError(
                f'Error spliting CSV line - line is {csv_line}'
            ) from e
        return cls(num, start, duration, direction)

    @classmethod
    def from_csv_file(cls, file):
        with open(file, 'r') as f:
            while True:
                line = f.readline()
                if not line:
                    break
                yield cls.from_csv(line)

def findMostExpensiveNumber(callLogFilepath):
    calls = PhoneCall.from_csv_file(callLogFilepath)
    #
    # Build up a mapping table of phone numbers and total call cost.
    # The table will be in the format
    # {
    #   number: [number, total_cost],
    #   number: [number, total_cost],
    #   ...
    # }
    # The number is the dictionary key to simplify insertions, and it is
    # duplicated in the value to allow us to easily sort the values according
    # to total cost and then grab the number associated with the greatest cost
    number_table = dict()
    for call in calls:
        number_table.setdefault(
            call.number.number, [call.number.number, 0]
        )[1] += call.cost()
    print(number_table)
    return 0

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} <Call log file>')
        sys.exit(1)
    print(findMostExpensiveNumber(sys.argv[1]))
    sys.exit(0)