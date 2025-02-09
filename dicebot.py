#!/usr/bin/env python3
from flask import Flask
from flask import request
from flask import jsonify
import random
import traceback

'''
This is a slack slash command dicebot.

Slack slash commands can be run against this command.

And various dice can be rolled.

The following options exist:
 - /roll - this rolls the number of dice provided and adds or subtracts and modifiers.
 For example, /roll 2d10 +3 will roll 2x 6 sided dice and then add 3 to the result.

 - /adv - this will roll 2x 20 sided dice, returns the highest result with any modifiers.
 For example, /adv +2 will roll 2d20 then add 2 to the highest result.

 - /dis - this will roll 2x 20 sided dice, then returns the lowest result with any modifiers.
 For example, /dis -3 will roll 2d20 then subtract 3 from the lowest result.

 - /character - this rolls 4x 6 sided dice, dropping the lowest value. This is done 6 times.
 This is useful for one command character creation.
 For example, /character will return 6 values
'''

app = Flask(__name__)

debug = False


class DicebotException(Exception):
    '''
    A custom exception to simplify error handling.

    If debug is true, then the error will also be sent to the hosting log.
    '''
    def __init__(self, value):
        self.value = value
        if debug:
            print(value)

    def __str__(self):
        return str(self.value)


def parse_roll(input_string, adv_or_dis=False, character=False):
    '''
    Takes in a roll_string from the slack command.
    Expected format is <num_dice>d<die_value>.
    Examples: 1d4, 2d6, 3d8, 99d100

    A valid roll can also include "+<num>" or "-<num>"
    Spaces are allowed on either side of the +/-

    Examples: 4d4 + 2, 2d6+1, 8d12 +11

    Valid numbers are between 1d1 and 99d100

    adv_or_dis = True means that the roll will be set to 2d20
    character = True means the roll will be set to 3d6

    returns a dict of:
    {"num_dice": int(number_of_dice),
     "die": int(die),
     "modifier": modifier}
    '''
    try:
        if adv_or_dis:
            if debug:
                print("Rolling adv/dis")
            # Need to append the input_string in case there are modifiers
            # Let the rest of the function determine if the input_string is valid
            input_roll_string = "2d20" + str(input_string)

        elif character:
            if debug:
                print("Rolling character")
            # Stat blocks do not have modifiers, so ignore any input.
            input_roll_string = "3d6"

        else:
            if debug:
                print("normal roll")
            input_roll_string = str(input_string)
    except:
        print(input_string)  # capture the input string if it's invalid
        raise DicebotException("Invalid roll or modifier")

    # Remove the whitespace
    roll_string = input_roll_string.replace(" ", "")

    # 1d6 is minimum roll string length
    # 100d100+100 is the maximum roll string
    if len(roll_string) < 3 or len(roll_string) > 11:
        raise DicebotException("Roll string too short. Given " + roll_string)

    d_position = roll_string.find("d")

    if d_position < 0:
        raise DicebotException("'d' found in incorrect position. Given " + input_roll_string)

    num_dice = roll_string[:d_position]

    # Because I'm not above giving StackOverflow some credit
    # https://stackoverflow.com/questions/27050570/how-would-i-account-for-negative-values-in-python
    try:
        int(num_dice)
    except:
        raise DicebotException("Non digit found in the number of dice provided. Given " + input_roll_string)

    plus_pos = roll_string.find("+")
    minus_pos = roll_string.find("-")

    if plus_pos > 0:  # We have a + modifier
        die_value = roll_string[d_position + 1:plus_pos]
        if len(die_value) == 0:
            raise DicebotException("No dice value provided. Given " + input_roll_string)

        roll_modifier = roll_string[plus_pos + 1:]

    elif minus_pos > 0:  # We have a - modifier
        die_value = roll_string[d_position + 1:minus_pos]
        if len(die_value) == 0:
            raise DicebotException("No dice value provided. Given " + input_roll_string)

        roll_modifier = roll_string[minus_pos:]

    else:  # No modifier exists. Mark it zero dude.
        die_value = roll_string[d_position + 1:]
        if len(die_value) == 0:
            raise DicebotException("No dice value provided. Given " + input_roll_string)

        roll_modifier = 0

    try:
        int(die_value)
    except:
        raise DicebotException("Non digit found in the dice value. Given " + input_roll_string)

    if int(die_value) <= 0:
        raise DicebotException("Die value can not be 0 or less. Given " + input_roll_string)

    if int(num_dice) <= 0:
        raise DicebotException("Number of dice can not be 0 or less. Given " + input_roll_string)

    # This will accept modifiers like "2-3" (and consider it -1)
    try:
        int(roll_modifier)
    except:
        raise DicebotException("Invalid roll modifer. Given " + str(input_roll_string))

    return {"num_dice": int(num_dice),
            "die": int(die_value),
            "modifier": int(roll_modifier)}


def generate_roll(roll_dict):
    '''
    Takes in a valid roll string and returns the sum of the roll with modifiers.
    Assumes roll_list is a dict containing:
    {"num_dice": <int>, "die": <int>, "modifier": <int>}

    The input is assumed to have been passed from parse_roll()

    Returns dict containing {"total": <int>, "modifer": <modifer_int>, "rolls": [roll_int]}
    '''

    if not isinstance(roll_dict, dict):
        print(roll_dict)
        raise DicebotException("generate_roll was not passed a dict()")

    # Check the fields we need in roll_dict exist
    if "num_dice" not in roll_dict or "die" not in roll_dict or "modifier" not in roll_dict:
        print(roll_dict)
        raise DicebotException("Missing dictionary key in roll_dict.")

    try:
        num_dice = int(roll_dict["num_dice"])
        die_value = int(roll_dict["die"])
        modifier = int(roll_dict["modifier"])
    except:
        print(roll_dict)
        raise DicebotException("Roll dict contains non-numbers.")

    if num_dice <= 0:
        raise DicebotException("Invalid number of dice. Passed " + str(roll_dict))

    if die_value <= 0:
        raise DicebotException("Invalid die value. Passed " + str(roll_dict))

    rolls = []
    for x in range(0, num_dice):
        roll_result = random.randint(1, die_value)
        rolls.append(roll_result)

    return {"total": sum(rolls) + modifier,
            "rolls": rolls,
            "modifier": modifier}


def parse_slack_message(slack_message):
    '''
    Consumes a slack POST message that was sent in JSON format.

    Validates the fields and passes back a simplified dict containing:
    {
    "username":<slack_username>,
    "command":<slash_command>,
    "text":<slash_command_arguments>,
    "channel_name":<slack_channel_command_issued_in>
    }

    Slack POST messages send JSON that looks like the following:
    {"token": "uto4ItLoT82ceQoBpIvgtzzz",
              "team_id": "T0C3TFAGL",
              "team_domain": "my_team_name",
              "channel_id": "D0C3VQDAS",
              "channel_name": "directmessage",
              "user_id": "U0C3TFAQ4",
              "user_name": "my_username",
              "command": "/weather",
              "text": "2d6",
              "response_url": "https://hooks.slack.com/commands/T0C3TFAGL/112373954929/8k4mT8sMpIRdslA0IOMKvWSS"}
    '''

    if "user_name" not in slack_message:
        raise DicebotException("Invalid Slack message, no user_name in slack message: " + slack_message)

    if "command" not in slack_message:
        raise DicebotException("No command in slack message: " + slack_message)

    if "text" not in slack_message:
        raise DicebotException("No text in slack message: " + slack_message)

    if "channel_name" not in slack_message:
        raise DicebotException("No channel in slack message: " + slack_message)

    return {"username": slack_message["user_name"],
            "command": slack_message["command"],
            "text": slack_message["text"],
            "channel_name": slack_message["channel_name"]}


def generate_slack_response(text, in_channel=True):
    '''
    Consumes a string message to send to slack in a public format.

    If the message should be sent only to the user set in_channel=False
    '''

    # If you wish to add slack token validation without putting the values in source
    # Heroku env variables can be set on the heroku console
    # and checked with this code
    #
    # if SLACK_WEBHOOK in os.environ:
    #      webhook = os.environ["SLACK_WEBHOOK"]
    #      token = os.environ["SLACK_TOKEN"]

    if in_channel:
        where = "in_channel"
    else:
        where = "ephemeral"
    response = dict()
    response["response_type"] = where
    response["text"] = text
    response["attachments"] = []

    if debug:
        print("Slack Response: " + str(response))

    return jsonify(response)


def format_standard_roll(rolled_dice, username, roll):
    '''
    Takes in a rolled_dice dict, slack username and the original parsed roll
    and returns a string.

    rolled_dice is the output from generate_roll
    roll is the output from parse_roll

    This assumes the output should be for a standard dice roll (e.g., 2d6 +2).
    Other roll formats require their own formatting methods.

    Format returned is
        <username> rolled <num>d<die> (+)<modifier>
        <roll> + <roll> + <roll> (+)<modifier> = *<total>*

    '''
    try:
        # This is done to make output easier and to validate the inputs are strings
        string_number_list = list(map(str, rolled_dice["rolls"]))
    except:
        print(rolled_dice)
        raise DicebotException("format_standard_roll passed values that can't be cast to string")

    output_text = []
    output_text.append("_")
    try:
        output_text.append(username + " rolled " + str(roll["num_dice"]) + "d" + str(roll["die"]) + " = ")
    except:
        raise DicebotException("format_standard_roll could not cast roll values to string.")

    # output_text.append("\n")
    
    # printed_first_roll = False

    # for roll in string_number_list:

    #     # Only put a "+" after the first roll
    #     if printed_first_roll:
    #         output_text.append(" + ")

    #     output_text.append(roll)
    #     printed_first_roll = True

    # if rolled_dice["modifier"] > 0:
    #     output_text.append(" (+" + str(rolled_dice["modifier"]) + ")")

    # if rolled_dice["modifier"] < 0:
    #     # Negative modifiers are "-2" so no need to prepend "-"
    #     output_text.append(" (" + str(rolled_dice["modifier"]) + ")")

    # output_text.append(" = ")
    output_text.append("*" + str(rolled_dice["total"]) + "*")
    output_text.append("_")
    output_text.append("\n")

    # Italicize the bot response
    return "".join(output_text)


def format_adv_dis_roll(rolled_dice, username, roll, adv=False, dis=False):
    '''
    Takes in a generate_roll dict, slack username, and original parsed roll.
    Set adv=True or dis=True based on what formatting to return.

    Returns a string ready to be passed to the slack message builder.

    Format is
        <username> rolled at [advantage | disadvantage] (+) <modifier>
        <roll> ~<roll>~ ((+)<modifier>) = *<total>*

    The ignored roll is printed with strikethrough.
    '''

    output_text = []
    try:
        if adv:
            output_text.append(str(username) + " rolled at Advantage:")
        if dis:
            output_text.append(str(username) + " rolled at Disadvantage:")
    except:
        print(username)
        raise DicebotException("format_adv_dis_roll could not cast roll values to string.")

    output_text.append("\n")

    if roll["num_dice"] != 2:
        print(roll)
        raise DicebotException("Trying to format adv/dis roll with more than 2d20")

    if adv:
        try:
            if rolled_dice["rolls"][0] >= rolled_dice["rolls"][1]:
                output_text.append("*" + str(rolled_dice["rolls"][0]) + "*")
                output_text.append(" ")
                output_text.append("~" + str(rolled_dice["rolls"][1]) + "~")
                result = rolled_dice["rolls"][0]
            if rolled_dice["rolls"][1] > rolled_dice["rolls"][0]:
                output_text.append("~" + str(rolled_dice["rolls"][0]) + "~")
                output_text.append(" ")
                output_text.append("*" + str(rolled_dice["rolls"][1]) + "*")
                result = rolled_dice["rolls"][1]
        except:
            print(traceback.format_exc())
            raise DicebotException("format_adv_dis_roll had a problem rolling at advantage")

    if dis:
        try:
            if rolled_dice["rolls"][0] <= rolled_dice["rolls"][1]:
                output_text.append("*" + str(rolled_dice["rolls"][0]) + "*")
                output_text.append(" ")
                output_text.append("~" + str(rolled_dice["rolls"][1]) + "~")
                result = rolled_dice["rolls"][0]
            if rolled_dice["rolls"][1] < rolled_dice["rolls"][0]:
                output_text.append("~" + str(rolled_dice["rolls"][0]) + "~")
                output_text.append(" ")
                output_text.append("*" + str(rolled_dice["rolls"][1]) + "*")
                result = rolled_dice["rolls"][1]
        except:
            print(traceback.format_exc())
            raise DicebotException("format_adv_dis_roll had a problem rolling at disadvantage")

    if rolled_dice["modifier"] > 0:
        output_text.append(" (+" + str(rolled_dice["modifier"]) + ")")
    if rolled_dice["modifier"] < 0:
        output_text.append(" (" + str(rolled_dice["modifier"]) + ")")

    output_text.append(" = ")
    output_text.append("*" + str((result + rolled_dice["modifier"])) + "*")
    output_text.append("\n")

    return "".join(output_text)


def format_character_roll(roll_list, username):
    '''
    Takes in a a list of 6 generate_roll dicts and the slack username
    Indicates the low and total for each roll dict.
    Returns a string ready to be passed to the slack message builder.

    Format is:
    <username> rolled a stat block:
    ~<low>~ <num> + <num> + <num> = *<total>*
    ~<low>~ <num> + <num> + <num> = *<total>*
    ~<low>~ <num> + <num> + <num> = *<total>*
    ~<low>~ <num> + <num> + <num> = *<total>*
    ~<low>~ <num> + <num> + <num> = *<total>*
    ~<low>~ <num> + <num> + <num> = *<total>*
    '''

    output_text = []
    try:
        output_text.append(str(username) + " rolled a stat block:")
    except:
        print(username)
        raise DicebotException("format_character_roll username is not a string")

    output_text.append("\n")

    if len(roll_list) != 6:
        print(roll_list)
        raise DicebotException("Incorrect number of rolls in the stat block")

    # {"total": <int>, "modifer": <modifer_int>, "rolls": [roll_int]}
    for roll in roll_list:
        try:
            sorted_rolls = sorted(roll["rolls"], key=int)
            output_text.append("~" + str(sorted_rolls[0]) + "~ ")
            output_text.append(str(sorted_rolls[1]) + " + ")
            output_text.append(str(sorted_rolls[2]) + " + ")
            output_text.append(str(sorted_rolls[3]) + " = ")
            output_text.append("*" + str(sorted_rolls[1] + sorted_rolls[2] + sorted_rolls[3]) + "*")
        except:
            print(traceback.format_exc())
            raise DicebotException("Unable to print statblock")

        output_text.append("\n")

    return "".join(output_text)

# Handle standard rolls in the style 2d6 +3
@app.route('/roll', methods=["GET", "POST"])
def test_roll():

    if debug:
        print(request.form)

    try:
        # First parse the inbound slack message and get a simple dict
        slack_dict = parse_slack_message(request.form)

        # Next, parse and validate the roll from slack
        parsed_roll = parse_roll(slack_dict["text"])

        # Roll all the dice we've been asked to roll
        rolled_dice = generate_roll(parsed_roll)

        # Build the message to send back to slack based on the rolled dice,
        # the user who asked and the original dice they asked to roll.
        output = format_standard_roll(rolled_dice, slack_dict["username"], parsed_roll)

    # Any errors thrown will all be caught right here.
    except DicebotException as dbe:
        return generate_slack_response("error: " + str(dbe) + \
                                       "\n Please use /roll <num>d<num> (+/-)<num>",
                                       in_channel=False)
    except:
        # Ending up here means an exception was thrown that we didn't catch. A bug.
        print("Unhandled traceback in /roll")
        print(traceback.format_exc)
        return generate_slack_response("Hmm....something went wrong. Try again?", in_channel=False)

    return generate_slack_response(output)


# Handle rolling at advantage
# Roll 2d20 and drop the low
@app.route('/adv', methods=["GET", "POST"])
def adv_roll():

    if debug:
        print(request.form)

    try:
        # Parse the incoming slack JSON message
        slack_dict = parse_slack_message(request.form)

        # Parse the input, but set it to only roll 2d20
        parsed_roll = parse_roll(slack_dict["text"], adv_or_dis=True)

        # Roll the 2d20 and modifier
        rolled_dice = generate_roll(parsed_roll)

        # Build the result of the rolls
        output = format_adv_dis_roll(rolled_dice, slack_dict["username"], parsed_roll, adv=True)

    except DicebotException as dbe:
        return generate_slack_response("error: " + str(dbe) + "\n Please use /adv (+/-)<num>", in_channel=False)
    except:
        print("Unhandled traceback in /adv")
        print(traceback.format_exc())
        return generate_slack_response("Hmm....something went wrong. Try again?", in_channel=False)

    return generate_slack_response(output)


# Handle rolling at disadvantage
# Roll 2d20 and drop the high
@app.route('/dis', methods=["GET", "POST"])
def dis_roll():

    if debug:
        print(request.form)

    try:
        #Parse the incoming slack JSON message
        slack_dict = parse_slack_message(request.form)

        # Parse the input, but set it to only roll 2d20
        parsed_roll = parse_roll(slack_dict["text"], adv_or_dis=True)

        # Roll 2d20 and modifiers
        rolled_dice = generate_roll(parsed_roll)

        # Build the output
        output = format_adv_dis_roll(rolled_dice, slack_dict["username"], parsed_roll, dis=True)

    except DicebotException as dbe:
        return generate_slack_response("error: " + str(dbe) + "\n Please use /dis (+/-)<num>", in_channel=False)
    except:
        print("Unhandled traceback in /dis")
        print(traceback.format_exc())
        return generate_slack_response("Hmm....something went wrong. Try again?", in_channel=False)

    return generate_slack_response(output)


# Build a new character stat block
# Roll 4d6 and drop the low. Do it 6 times
@app.route('/character', methods=["GET", "POST"])
def character():
    if debug:
        print(request.form)

    try:
        # Parse the incoming Slack JSON
        slack_dict = parse_slack_message(request.form)

        # Build a roll dict, but ignore all inputs (dice or modifiers)
        parsed_roll = parse_roll(slack_dict["text"], character=True)

        # This will hold the dict of the roll result.
        roll = []
        for x in range(6): # Roll 4d6, 6 times
            roll.append(generate_roll(parsed_roll))

        # Build the output
        output = format_character_roll(roll, slack_dict["username"])

    except DicebotException as dbe:
        return generate_slack_response("error: " + str(dbe) + "\n Please use /character", in_channel=False)
    except:
        print("Unhandled traceback in /character")
        print(traceback.format_exc())
        return generate_slack_response("Hmm....something went wrong. Try again?", in_channel=False)

    return generate_slack_response(output)


if __name__ == "__main__":
    app.run()
