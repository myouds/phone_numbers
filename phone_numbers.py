#!/usr/bin/env python3

import datetime
from enum import Enum
import math
import json


class CallParseError(Exception):
    pass


class Direction(Enum):
    INCOMING = 'INCOMING'
    OUTGOING = 'OUTGOING'


class PhoneNumber:
    '''
    Phone number superclass. This should not be instantiated directly.
    Always use one of the subclasses.
    '''
    cost_per_minute = None
    connection_charge = None
    off_peak_divider = None

    def __init__(self, number):
        if self.cost_per_minute is None or self.connection_charge is None:
            raise NotImplementedError('Cannot instantiate generic PhoneNumber')
        self.number = number

    @classmethod
    def from_string(cls, number):
        '''
        Take a phone number in string form and return one of the PhoneNumber
        subclasses. The choice of subclass will depend on the first characters
        of the phone number
        '''
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
        if number[0:3] == '080':
            return FreeNumber(number)
        #
        # Mobile numbers start with 07
        if number[0:2] == '07':
            #
            # Unless it is 076 and not 07624
            if number[2] != '6' or number[0:5] == '07624':
                return MobileNumber(number)
        #
        # Everything else is invalid
        return InvalidNumber(number)

#
# Various classes of number have different costs
#


class InternationalNumber(PhoneNumber):
    cost_per_minute = 80
    connection_charge = 50


class LandlineNumber(PhoneNumber):
    cost_per_minute = 15
    connection_charge = 0
    off_peak_divider = 3


class MobileNumber(PhoneNumber):
    cost_per_minute = 30
    connection_charge = 0
    off_peak_divider = 3


class FreeNumber(PhoneNumber):
    cost_per_minute = 0
    connection_charge = 0


class InvalidNumber(PhoneNumber):
    cost_per_minute = 0
    connection_charge = 0


#
# Tarriff includes free minutes for some number classes
#
international_allowance = 10
landline_mobile_allowance = 100


class PhoneCall:
    peak_time_start = datetime.time(8, 0)
    peak_time_end = datetime.time(20, 0)

    def __init__(self, number, start_time, duration, direction):
        global international_allowance
        global landline_mobile_allowance
        #
        # Phone number class will depend on its first characters
        self.number = PhoneNumber.from_string(number)
        #
        # Start time is in ISO 8601 format but may end with 'Z' instead of
        # the +00:00 expected by datetime
        try:
            self.start_time = datetime.datetime.fromisoformat(
                start_time.replace('Z', '+00:00')
            )
        except Exception as e:
            raise CallParseError(
                f'Error parsing start time {start_time}'
            ) from e
        #
        # Duration is in the format 'MM:SS'.
        # We need the number of started minutes
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
        #
        # Work out how much of the tarriff allowance this call has used
        # and reduce the remaining allowance accordingly.
        if self.direction is Direction.OUTGOING:
            if type(self.number) is InternationalNumber:
                self.free_minutes = min(
                    self.duration,
                    international_allowance
                )
                international_allowance -= self.free_minutes
            elif type(self.number) in [LandlineNumber, MobileNumber]:
                self.free_minutes = min(
                    self.duration,
                    landline_mobile_allowance
                )
                landline_mobile_allowance -= self.free_minutes
            else:
                self.free_minutes = 0

    def cost(self, apply_allowance=True):
        if self.direction == Direction.INCOMING:
            return 0
        #
        # Charge is per started minute with an additional connection charge
        # Subtract the free minutes from the started minutes
        if apply_allowance:
            chargeable_minutes = self.duration - self.free_minutes
        else:
            #
            # Free minutes can be optionally ignored for testing purposes
            chargeable_minutes = self.duration
        cost = self.number.connection_charge + \
            (chargeable_minutes * self.number.cost_per_minute)

        if self.number.off_peak_divider is not None:
            start_time = self.start_time.time()
            if start_time < self.peak_time_start \
                    or start_time > self.peak_time_end:
                #
                # Off peak start time - divide cost by divider
                cost = cost // self.number.off_peak_divider
        return cost

    @classmethod
    def from_csv(cls, csv_line):
        #
        # CSV line should be in the format:
        # PhoneNumber,CallStartTime,CallDuration,CallDirection
        try:
            num, start, duration, direction = csv_line.rstrip('\n').split(',')
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
                if len(line) > 1:
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
    two_most_expensive = sorted(
        number_table.values(), key=lambda x: x[1], reverse=True
    )[0:2]
    #
    # Return None if there has been no cost
    if two_most_expensive[0][1] == 0:
        return None
    #
    # Return None if it is a tie
    if len(two_most_expensive) == 2 and \
            two_most_expensive[0][1] == two_most_expensive[1][1]:
        return None
    most_expensive = two_most_expensive[0]
    return_data = dict(
        PhoneNumber=most_expensive[0],
        TotalAmount='£%f' % (most_expensive[1] / 100)
    )
    #
    # Set ensure_ascii=False to allow the £ sign to be printed properly
    return json.dumps(return_data, indent=4, ensure_ascii=False)

#
# Tests to be run by pytest
#


def test_phone_number():
    numbers = [
        ('07777777777', MobileNumber),
        ('07655555555', InvalidNumber),
        ('07624777777', MobileNumber),
        ('01858585858', LandlineNumber),
        ('02934567890', LandlineNumber),
        ('+441234565567', LandlineNumber),
        ('00441234565567', LandlineNumber),
        ('00011234565567', InternationalNumber),
        ('+011234565567', InternationalNumber),
        ('+11234565567', InternationalNumber),
        ('05678765432', InvalidNumber)
    ]
    for num in numbers:
        assert type(PhoneNumber.from_string(num[0])) is num[1]


def test_csv():
    csv = '07882456789,2019-08-29T11:28:05.666Z,12:36,OUTGOING'
    assert PhoneCall.from_csv(csv).cost(apply_allowance=False) == 390
    csv = '07882456789,2019-08-29T20:28:05.666Z,12:36,OUTGOING'
    assert PhoneCall.from_csv(csv).cost(apply_allowance=False) == 130
    csv = '07882456789,2019-08-29T20:28:05.666Z,12:36,INCOMING'
    assert PhoneCall.from_csv(csv).cost(apply_allowance=False) == 0
    csv = '08082456789,2019-08-29T20:28:05.666Z,12:36,OUTGOING'
    assert PhoneCall.from_csv(csv).cost(apply_allowance=False) == 0
    csv = '+017654765234,2019-08-29T15:28:05.666Z,1:0,OUTGOING'
    assert PhoneCall.from_csv(csv).cost(apply_allowance=False) == 130


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} <Call log file>')
        sys.exit(1)
    print(findMostExpensiveNumber(sys.argv[1]))
    sys.exit(0)
