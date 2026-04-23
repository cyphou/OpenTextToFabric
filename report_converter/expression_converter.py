"""BIRT JavaScript expression → DAX converter.

Maps BIRT report expressions (JavaScript-based) to DAX equivalents.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# BIRT JavaScript function → DAX mapping
# Format: (birt_pattern, dax_replacement, is_regex)
FUNCTION_MAP: list[tuple[str, str, bool]] = [
    # Aggregation functions
    (r"Total\.sum\(([^)]+)\)", r"SUM(\1)", True),
    (r"Total\.count\(\)", "COUNTROWS()", True),
    (r"Total\.count\(([^)]+)\)", r"COUNT(\1)", True),
    (r"Total\.ave\(([^)]+)\)", r"AVERAGE(\1)", True),
    (r"Total\.max\(([^)]+)\)", r"MAX(\1)", True),
    (r"Total\.min\(([^)]+)\)", r"MIN(\1)", True),
    (r"Total\.runningSum\(([^)]+)\)", r"CALCULATE(SUM(\1), FILTER(ALL(), [__row_number] <= EARLIER([__row_number])))", True),
    (r"Total\.runningCount\(\)", "CALCULATE(COUNTROWS(), FILTER(ALL(), [__row_number] <= EARLIER([__row_number])))", True),
    (r"Total\.percentSum\(([^)]+)\)", r"DIVIDE(SUM(\1), CALCULATE(SUM(\1), ALL()))", True),
    (r"Total\.percentRank\(([^)]+)\)", r"RANKX(ALL(), \1) / COUNTROWS(ALL())", True),
    (r"Total\.rank\(([^)]+)\)", r"RANKX(ALL(), \1)", True),
    (r"Total\.weightedAvg\(([^,]+),\s*([^)]+)\)", r"SUMX(VALUES(), \1 * \2) / SUM(\2)", True),
    (r"Total\.countDistinct\(([^)]+)\)", r"DISTINCTCOUNT(\1)", True),
    (r"Total\.variance\(([^)]+)\)", r"VAR.S(\1)", True),
    (r"Total\.stdDev\(([^)]+)\)", r"STDEV.S(\1)", True),
    (r"Total\.median\(([^)]+)\)", r"MEDIAN(\1)", True),
    (r"Total\.mode\(([^)]+)\)", r"MINX(TOPN(1, ADDCOLUMNS(VALUES(\1), \"@cnt\", CALCULATE(COUNTROWS())), [@cnt], DESC), \1)", True),

    # String functions
    (r"BirtStr\.toUpper\(([^)]+)\)", r"UPPER(\1)", True),
    (r"BirtStr\.toLower\(([^)]+)\)", r"LOWER(\1)", True),
    (r"BirtStr\.trim\(([^)]+)\)", r"TRIM(\1)", True),
    (r"BirtStr\.trimLeft\(([^)]+)\)", r"TRIM(\1)", True),
    (r"BirtStr\.trimRight\(([^)]+)\)", r"TRIM(\1)", True),
    (r"BirtStr\.left\(([^,]+),\s*(\d+)\)", r"LEFT(\1, \2)", True),
    (r"BirtStr\.right\(([^,]+),\s*(\d+)\)", r"RIGHT(\1, \2)", True),
    (r"BirtStr\.indexOf\(([^,]+),\s*([^)]+)\)", r"SEARCH(\2, \1, 1, 0)", True),
    (r"BirtStr\.length\(([^)]+)\)", r"LEN(\1)", True),
    (r"BirtStr\.charLength\(([^)]+)\)", r"LEN(\1)", True),
    (r"BirtStr\.concat\(([^,]+),\s*([^)]+)\)", r"\1 & \2", True),
    (r"BirtStr\.replace\(([^,]+),\s*([^,]+),\s*([^)]+)\)", r"SUBSTITUTE(\1, \2, \3)", True),
    (r"BirtStr\.search\(([^,]+),\s*([^)]+)\)", r"SEARCH(\2, \1)", True),

    # Date/time functions
    (r"BirtDateTime\.now\(\)", "NOW()", True),
    (r"BirtDateTime\.today\(\)", "TODAY()", True),
    (r"BirtDateTime\.year\(([^)]+)\)", r"YEAR(\1)", True),
    (r"BirtDateTime\.month\(([^)]+)\)", r"MONTH(\1)", True),
    (r"BirtDateTime\.day\(([^)]+)\)", r"DAY(\1)", True),
    (r"BirtDateTime\.hour\(([^)]+)\)", r"HOUR(\1)", True),
    (r"BirtDateTime\.minute\(([^)]+)\)", r"MINUTE(\1)", True),
    (r"BirtDateTime\.second\(([^)]+)\)", r"SECOND(\1)", True),
    (r"BirtDateTime\.quarter\(([^)]+)\)", r"QUARTER(\1)", True),
    (r"BirtDateTime\.weekOfYear\(([^)]+)\)", r"WEEKNUM(\1)", True),
    (r"BirtDateTime\.dayOfWeek\(([^)]+)\)", r"WEEKDAY(\1)", True),
    (r"BirtDateTime\.dayOfYear\(([^)]+)\)", r"DATEDIFF(DATE(YEAR(\1), 1, 1), \1, DAY) + 1", True),
    (r"BirtDateTime\.diffYear\(([^,]+),\s*([^)]+)\)", r"DATEDIFF(\1, \2, YEAR)", True),
    (r"BirtDateTime\.diffMonth\(([^,]+),\s*([^)]+)\)", r"DATEDIFF(\1, \2, MONTH)", True),
    (r"BirtDateTime\.diffDay\(([^,]+),\s*([^)]+)\)", r"DATEDIFF(\1, \2, DAY)", True),
    (r"BirtDateTime\.addYear\(([^,]+),\s*([^)]+)\)", r"DATEADD(\1, \2, YEAR)", True),
    (r"BirtDateTime\.addMonth\(([^,]+),\s*([^)]+)\)", r"DATEADD(\1, \2, MONTH)", True),
    (r"BirtDateTime\.addDay\(([^,]+),\s*([^)]+)\)", r"DATEADD(\1, \2, DAY)", True),

    # Math functions
    (r"BirtMath\.round\(([^,]+),\s*(\d+)\)", r"ROUND(\1, \2)", True),
    (r"BirtMath\.round\(([^)]+)\)", r"ROUND(\1, 0)", True),
    (r"BirtMath\.roundUp\(([^,]+),\s*(\d+)\)", r"ROUNDUP(\1, \2)", True),
    (r"BirtMath\.roundDown\(([^,]+),\s*(\d+)\)", r"ROUNDDOWN(\1, \2)", True),
    (r"BirtMath\.ceiling\(([^)]+)\)", r"CEILING(\1, 1)", True),
    (r"BirtMath\.floor\(([^)]+)\)", r"FLOOR(\1, 1)", True),
    (r"BirtMath\.abs\(([^)]+)\)", r"ABS(\1)", True),
    (r"BirtMath\.mod\(([^,]+),\s*([^)]+)\)", r"MOD(\1, \2)", True),
    (r"BirtMath\.power\(([^,]+),\s*([^)]+)\)", r"POWER(\1, \2)", True),
    (r"BirtMath\.sqrt\(([^)]+)\)", r"SQRT(\1)", True),
    (r"BirtMath\.log\(([^)]+)\)", r"LN(\1)", True),
    (r"BirtMath\.log10\(([^)]+)\)", r"LOG(\1, 10)", True),
    (r"BirtMath\.exp\(([^)]+)\)", r"EXP(\1)", True),
    (r"BirtMath\.sign\(([^)]+)\)", r"SIGN(\1)", True),
    (r"BirtMath\.pi\(\)", "PI()", True),
    (r"BirtMath\.random\(\)", "RAND()", True),
    (r"BirtMath\.max\(([^,]+),\s*([^)]+)\)", r"MAX(\1, \2)", True),
    (r"BirtMath\.min\(([^,]+),\s*([^)]+)\)", r"MIN(\1, \2)", True),
    (r"BirtMath\.safeDivide\(([^,]+),\s*([^)]+)\)", r"DIVIDE(\1, \2, 0)", True),
    (r"BirtMath\.truncate\(([^,]+),\s*(\d+)\)", r"TRUNC(\1, \2)", True),
    (r"BirtMath\.truncate\(([^)]+)\)", r"TRUNC(\1, 0)", True),

    # Type conversion
    (r"BirtComp\.toInteger\(([^)]+)\)", r"INT(\1)", True),
    (r"BirtComp\.toDouble\(([^)]+)\)", r"VALUE(\1)", True),
    (r"BirtComp\.toString\(([^)]+)\)", r"FORMAT(\1, \"\")", True),
    (r"BirtComp\.toDate\(([^)]+)\)", r"DATEVALUE(\1)", True),
    (r"BirtComp\.toBoolean\(([^)]+)\)", r"IF(\1, TRUE(), FALSE())", True),

    # Conditional
    (r"BirtComp\.ifNull\(([^,]+),\s*([^)]+)\)", r"IF(ISBLANK(\1), \2, \1)", True),
    (r"BirtComp\.nullIf\(([^,]+),\s*([^)]+)\)", r"IF(\1 = \2, BLANK(), \1)", True),

    # Formatting functions
    (r"BirtStr\.format\(([^,]+),\s*\"#,##0\"\)", r"FORMAT(\1, \"#,##0\")", True),
    (r"BirtStr\.format\(([^,]+),\s*\"#,##0\.00\"\)", r"FORMAT(\1, \"#,##0.00\")", True),
    (r"BirtStr\.format\(([^,]+),\s*([^)]+)\)", r"FORMAT(\1, \2)", True),
    (r"BirtDateTime\.format\(([^,]+),\s*([^)]+)\)", r"FORMAT(\1, \2)", True),

    # String extras
    (r"BirtStr\.toProperCase\(([^)]+)\)", r"UPPER(LEFT(\1, 1)) & LOWER(MID(\1, 2, LEN(\1)))", True),
    (r"BirtStr\.padLeft\(([^,]+),\s*(\d+),\s*([^)]+)\)", r"REPT(\3, \2 - LEN(\1)) & \1", True),
    (r"BirtStr\.padRight\(([^,]+),\s*(\d+),\s*([^)]+)\)", r"\1 & REPT(\3, \2 - LEN(\1))", True),
    (r"BirtStr\.contains\(([^,]+),\s*([^)]+)\)", r"CONTAINSSTRING(\1, \2)", True),
    (r"BirtStr\.startsWith\(([^,]+),\s*([^)]+)\)", r"LEFT(\1, LEN(\2)) = \2", True),
    (r"BirtStr\.endsWith\(([^,]+),\s*([^)]+)\)", r"RIGHT(\1, LEN(\2)) = \2", True),
    (r"BirtStr\.substr\(([^,]+),\s*([^,]+),\s*([^)]+)\)", r"MID(\1, \2 + 1, \3)", True),
    (r"BirtStr\.mid\(([^,]+),\s*([^,]+),\s*([^)]+)\)", r"MID(\1, \2, \3)", True),

    # Date extras
    (r"BirtDateTime\.firstDayOfMonth\(([^)]+)\)", r"DATE(YEAR(\1), MONTH(\1), 1)", True),
    (r"BirtDateTime\.lastDayOfMonth\(([^)]+)\)", r"EOMONTH(\1, 0)", True),
    (r"BirtDateTime\.firstDayOfYear\(([^)]+)\)", r"DATE(YEAR(\1), 1, 1)", True),
    (r"BirtDateTime\.lastDayOfYear\(([^)]+)\)", r"DATE(YEAR(\1), 12, 31)", True),
    (r"BirtDateTime\.addWeek\(([^,]+),\s*([^)]+)\)", r"DATEADD(\1, \2 * 7, DAY)", True),
    (r"BirtDateTime\.addHour\(([^,]+),\s*([^)]+)\)", r"\1 + TIME(\2, 0, 0)", True),
    (r"BirtDateTime\.addMinute\(([^,]+),\s*([^)]+)\)", r"\1 + TIME(0, \2, 0)", True),
    (r"BirtDateTime\.addSecond\(([^,]+),\s*([^)]+)\)", r"\1 + TIME(0, 0, \2)", True),
    (r"BirtDateTime\.diffHour\(([^,]+),\s*([^)]+)\)", r"INT((\2 - \1) * 24)", True),
    (r"BirtDateTime\.diffMinute\(([^,]+),\s*([^)]+)\)", r"INT((\2 - \1) * 24 * 60)", True),
    (r"BirtDateTime\.diffSecond\(([^,]+),\s*([^)]+)\)", r"INT((\2 - \1) * 24 * 60 * 60)", True),
    (r"BirtDateTime\.fiscalYear\(([^,]+),\s*(\d+)\)", r"IF(MONTH(\1) >= \2, YEAR(\1) + 1, YEAR(\1))", True),
    (r"BirtDateTime\.fiscalQuarter\(([^,]+),\s*(\d+)\)", r"INT(MOD(MONTH(\1) - \2 + 12, 12) / 3) + 1", True),

    # Advanced aggregations
    (r"Total\.first\(([^)]+)\)", r"FIRSTNONBLANK(\1, 1)", True),
    (r"Total\.last\(([^)]+)\)", r"LASTNONBLANK(\1, 1)", True),
    (r"Total\.movingAve\(([^,]+),\s*(\d+)\)", r"AVERAGEX(TOPN(\2, ALL(), [__row_number], DESC), \1)", True),
    (r"Total\.percentile\(([^,]+),\s*([^)]+)\)", r"PERCENTILE.INC(\1, \2)", True),
    (r"Total\.correlation\(([^,]+),\s*([^)]+)\)", r"DIVIDE(SUMX(ALL(), (\1 - AVERAGE(\1)) * (\2 - AVERAGE(\2))), SQRT(SUMX(ALL(), (\1 - AVERAGE(\1))^2) * SUMX(ALL(), (\2 - AVERAGE(\2))^2)))", True),
    (r"Total\.isTopN\(([^,]+),\s*(\d+)\)", r"RANKX(ALL(), \1, , DESC) <= \2", True),
    (r"Total\.isBottomN\(([^,]+),\s*(\d+)\)", r"RANKX(ALL(), \1, , ASC) <= \2", True),

    # ── Sprint 25: LOD / cross-tab aggregation expressions ──
    # BIRT cross-tab uses Total.sum with group filters → CALCULATE + FILTER
    (r"Total\.sumByGroup\(([^,]+),\s*([^)]+)\)", r"CALCULATE(SUM(\1), ALLEXCEPT(VALUES(\2)))", True),
    (r"Total\.countByGroup\(([^,]+),\s*([^)]+)\)", r"CALCULATE(COUNT(\1), ALLEXCEPT(VALUES(\2)))", True),
    (r"Total\.aveByGroup\(([^,]+),\s*([^)]+)\)", r"CALCULATE(AVERAGE(\1), ALLEXCEPT(VALUES(\2)))", True),
    (r"Total\.maxByGroup\(([^,]+),\s*([^)]+)\)", r"CALCULATE(MAX(\1), ALLEXCEPT(VALUES(\2)))", True),
    (r"Total\.minByGroup\(([^,]+),\s*([^)]+)\)", r"CALCULATE(MIN(\1), ALLEXCEPT(VALUES(\2)))", True),
    # Cross-tab percentage within group
    (r"Total\.percentOfGroup\(([^,]+),\s*([^)]+)\)", r"DIVIDE(SUM(\1), CALCULATE(SUM(\1), ALLEXCEPT(VALUES(\2))))", True),

    # ── Sprint 25: Window function mappings ──
    (r"Total\.runningAvg\(([^)]+)\)", r"CALCULATE(AVERAGE(\1), FILTER(ALL(), [__row_number] <= EARLIER([__row_number])))", True),
    (r"Total\.runningMax\(([^)]+)\)", r"CALCULATE(MAX(\1), FILTER(ALL(), [__row_number] <= EARLIER([__row_number])))", True),
    (r"Total\.runningMin\(([^)]+)\)", r"CALCULATE(MIN(\1), FILTER(ALL(), [__row_number] <= EARLIER([__row_number])))", True),
    (r"Total\.cumulativeSum\(([^)]+)\)", r"CALCULATE(SUM(\1), FILTER(ALL(), [__row_number] <= EARLIER([__row_number])))", True),
    (r"Total\.denseRank\(([^)]+)\)", r"RANKX(ALL(), \1, , DESC, Dense)", True),
    (r"Total\.rowNumber\(\)", r"RANKX(ALL(), [__row_number], , ASC)", True),
    (r"Total\.ntile\(([^,]+),\s*(\d+)\)", r"INT(RANKX(ALL(), \1, , ASC) * \2 / COUNTROWS(ALL())) + 1", True),
    (r"Total\.lag\(([^,]+),\s*(\d+)\)", r"LOOKUPVALUE(\1, [__row_number], [__row_number] - \2)", True),
    (r"Total\.lead\(([^,]+),\s*(\d+)\)", r"LOOKUPVALUE(\1, [__row_number], [__row_number] + \2)", True),

    # ── Sprint 25: Date/time intelligence ──
    (r"BirtDateTime\.dateTimeSpan\(([^,]+),\s*([^,]+),\s*\"year\"\)", r"DATEDIFF(\1, \2, YEAR)", True),
    (r"BirtDateTime\.dateTimeSpan\(([^,]+),\s*([^,]+),\s*\"month\"\)", r"DATEDIFF(\1, \2, MONTH)", True),
    (r"BirtDateTime\.dateTimeSpan\(([^,]+),\s*([^,]+),\s*\"day\"\)", r"DATEDIFF(\1, \2, DAY)", True),
    (r"BirtDateTime\.dateTimeSpan\(([^,]+),\s*([^,]+),\s*\"hour\"\)", r"DATEDIFF(\1, \2, HOUR)", True),
    (r"BirtDateTime\.formatDate\(([^,]+),\s*([^)]+)\)", r"FORMAT(\1, \2)", True),
    (r"BirtDateTime\.parseDate\(([^,]+),\s*([^)]+)\)", r"DATEVALUE(\1)", True),
    (r"BirtDateTime\.isWeekday\(([^)]+)\)", r"WEEKDAY(\1, 2) <= 5", True),
    (r"BirtDateTime\.isWeekend\(([^)]+)\)", r"WEEKDAY(\1, 2) > 5", True),
    (r"BirtDateTime\.endOfMonth\(([^)]+)\)", r"EOMONTH(\1, 0)", True),
    (r"BirtDateTime\.startOfMonth\(([^)]+)\)", r"DATE(YEAR(\1), MONTH(\1), 1)", True),
    (r"BirtDateTime\.startOfYear\(([^)]+)\)", r"DATE(YEAR(\1), 1, 1)", True),
    (r"BirtDateTime\.endOfYear\(([^)]+)\)", r"DATE(YEAR(\1), 12, 31)", True),
    (r"BirtDateTime\.startOfWeek\(([^)]+)\)", r"\1 - WEEKDAY(\1, 2) + 1", True),
    (r"BirtDateTime\.monthName\(([^)]+)\)", r"FORMAT(\1, \"MMMM\")", True),
    (r"BirtDateTime\.dayName\(([^)]+)\)", r"FORMAT(\1, \"dddd\")", True),
    (r"BirtDateTime\.isoWeek\(([^)]+)\)", r"WEEKNUM(\1, 21)", True),
    (r"BirtDateTime\.age\(([^,]+),\s*([^)]+)\)", r"DATEDIFF(\1, \2, YEAR)", True),

    # ── Sprint 25: Parameter → slicer wiring ──
    (r'params\["([^"]+)"\]\.displayText', r'SELECTEDVALUE([@\1])', True),
    (r"params\.([a-zA-Z_]\w*)\.value", r"[@\1]", True),
    (r"params\.([a-zA-Z_]\w*)\.displayText", r"SELECTEDVALUE([@\1])", True),

    # JavaScript Math → DAX
    (r"Math\.round\(([^)]+)\)", r"ROUND(\1, 0)", True),
    (r"Math\.ceil\(([^)]+)\)", r"CEILING(\1, 1)", True),
    (r"Math\.floor\(([^)]+)\)", r"FLOOR(\1, 1)", True),
    (r"Math\.abs\(([^)]+)\)", r"ABS(\1)", True),
    (r"Math\.pow\(([^,]+),\s*([^)]+)\)", r"POWER(\1, \2)", True),
    (r"Math\.sqrt\(([^)]+)\)", r"SQRT(\1)", True),
    (r"Math\.log\(([^)]+)\)", r"LN(\1)", True),
    (r"Math\.max\(([^,]+),\s*([^)]+)\)", r"MAX(\1, \2)", True),
    (r"Math\.min\(([^,]+),\s*([^)]+)\)", r"MIN(\1, \2)", True),
    (r"Math\.random\(\)", "RAND()", True),
    (r"Math\.PI", "PI()", True),

    # JavaScript String methods → DAX
    (r"\.toUpperCase\(\)", r"UPPER(\g<0>)", False),
    (r"\.toLowerCase\(\)", r"LOWER(\g<0>)", False),
    (r"\.trim\(\)", r"TRIM(\g<0>)", False),

    # ── Extended string functions ──
    (r"BirtStr\.toBase64\(([^)]+)\)", r"/* toBase64 unsupported in DAX */ \1", True),
    (r"BirtStr\.fromBase64\(([^)]+)\)", r"/* fromBase64 unsupported in DAX */ \1", True),
    (r"BirtStr\.reverse\(([^)]+)\)", r"/* REVERSE not in DAX */ \1", True),
    (r"BirtStr\.repeat\(([^,]+),\s*(\d+)\)", r"REPT(\1, \2)", True),
    (r"BirtStr\.capitalize\(([^)]+)\)", r"UPPER(LEFT(\1, 1)) & LOWER(MID(\1, 2, LEN(\1)))", True),
    (r"BirtStr\.isEmpty\(([^)]+)\)", r"ISBLANK(\1)", True),
    (r"BirtStr\.isNotEmpty\(([^)]+)\)", r"NOT(ISBLANK(\1))", True),
    (r"BirtStr\.countChar\(([^,]+),\s*([^)]+)\)", r"LEN(\1) - LEN(SUBSTITUTE(\1, \2, \"\"))", True),
    (r"BirtStr\.wrap\(([^,]+),\s*([^)]+)\)", r"\2 & \1 & \2", True),
    (r"BirtStr\.removeWhitespace\(([^)]+)\)", r"SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(\1, \" \", \"\"), UNICHAR(10), \"\"), UNICHAR(13), \"\")", True),

    # ── Extended date functions ──
    (r"BirtDateTime\.monthsBetween\(([^,]+),\s*([^)]+)\)", r"DATEDIFF(\1, \2, MONTH)", True),
    (r"BirtDateTime\.daysBetween\(([^,]+),\s*([^)]+)\)", r"DATEDIFF(\1, \2, DAY)", True),
    (r"BirtDateTime\.yearsBetween\(([^,]+),\s*([^)]+)\)", r"DATEDIFF(\1, \2, YEAR)", True),
    (r"BirtDateTime\.isLeapYear\(([^)]+)\)", r"IF(MOD(YEAR(\1), 400) = 0, TRUE(), IF(MOD(YEAR(\1), 100) = 0, FALSE(), IF(MOD(YEAR(\1), 4) = 0, TRUE(), FALSE())))", True),
    (r"BirtDateTime\.daysInMonth\(([^)]+)\)", r"DAY(EOMONTH(\1, 0))", True),
    (r"BirtDateTime\.daysInYear\(([^)]+)\)", r"DATEDIFF(DATE(YEAR(\1), 1, 1), DATE(YEAR(\1) + 1, 1, 1), DAY)", True),
    (r"BirtDateTime\.weekOfMonth\(([^)]+)\)", r"WEEKNUM(\1) - WEEKNUM(DATE(YEAR(\1), MONTH(\1), 1)) + 1", True),
    (r"BirtDateTime\.toUnixTimestamp\(([^)]+)\)", r"DATEDIFF(DATE(1970, 1, 1), \1, SECOND)", True),
    (r"BirtDateTime\.fromUnixTimestamp\(([^)]+)\)", r"DATE(1970, 1, 1) + \1 / 86400", True),
    (r"BirtDateTime\.isBusinessDay\(([^)]+)\)", r"WEEKDAY(\1, 2) <= 5", True),
    (r"BirtDateTime\.nextBusinessDay\(([^)]+)\)", r"IF(WEEKDAY(\1, 2) >= 5, \1 + (8 - WEEKDAY(\1, 2)), \1 + 1)", True),
    (r"BirtDateTime\.quarterStart\(([^)]+)\)", r"DATE(YEAR(\1), (QUARTER(\1) - 1) * 3 + 1, 1)", True),
    (r"BirtDateTime\.quarterEnd\(([^)]+)\)", r"EOMONTH(DATE(YEAR(\1), QUARTER(\1) * 3, 1), 0)", True),

    # ── Extended math functions ──
    (r"BirtMath\.safeDivide\(([^,]+),\s*([^,]+),\s*([^)]+)\)", r"DIVIDE(\1, \2, \3)", True),
    (r"BirtMath\.factorial\(([^)]+)\)", r"PRODUCTX(GENERATESERIES(1, \1), [Value])", True),
    (r"BirtMath\.gcd\(([^,]+),\s*([^)]+)\)", r"GCD(\1, \2)", True),
    (r"BirtMath\.lcm\(([^,]+),\s*([^)]+)\)", r"LCM(\1, \2)", True),
    (r"BirtMath\.clamp\(([^,]+),\s*([^,]+),\s*([^)]+)\)", r"MAX(\2, MIN(\3, \1))", True),
    (r"BirtMath\.lerp\(([^,]+),\s*([^,]+),\s*([^)]+)\)", r"\1 + (\2 - \1) * \3", True),
    (r"BirtMath\.percent\(([^,]+),\s*([^)]+)\)", r"DIVIDE(\1, \2) * 100", True),
    (r"BirtMath\.isEven\(([^)]+)\)", r"MOD(\1, 2) = 0", True),
    (r"BirtMath\.isOdd\(([^)]+)\)", r"MOD(\1, 2) <> 0", True),
    (r"BirtMath\.log2\(([^)]+)\)", r"LOG(\1, 2)", True),
    (r"BirtMath\.cbrt\(([^)]+)\)", r"POWER(\1, 1/3)", True),
    (r"BirtMath\.hypot\(([^,]+),\s*([^)]+)\)", r"SQRT(POWER(\1, 2) + POWER(\2, 2))", True),
    (r"BirtMath\.degrees\(([^)]+)\)", r"\1 * 180 / PI()", True),
    (r"BirtMath\.radians\(([^)]+)\)", r"\1 * PI() / 180", True),
    (r"BirtMath\.sin\(([^)]+)\)", r"SIN(\1)", True),
    (r"BirtMath\.cos\(([^)]+)\)", r"COS(\1)", True),
    (r"BirtMath\.tan\(([^)]+)\)", r"TAN(\1)", True),
    (r"BirtMath\.asin\(([^)]+)\)", r"ASIN(\1)", True),
    (r"BirtMath\.acos\(([^)]+)\)", r"ACOS(\1)", True),
    (r"BirtMath\.atan\(([^)]+)\)", r"ATAN(\1)", True),
    (r"BirtMath\.atan2\(([^,]+),\s*([^)]+)\)", r"ATAN2(\1, \2)", True),

    # ── Statistical functions ──
    (r"Total\.varianceP\(([^)]+)\)", r"VAR.P(\1)", True),
    (r"Total\.stdDevP\(([^)]+)\)", r"STDEV.P(\1)", True),
    (r"Total\.covarianceS\(([^,]+),\s*([^)]+)\)", r"SUMX(ALL(), (\1 - AVERAGE(\1)) * (\2 - AVERAGE(\2))) / (COUNTROWS(ALL()) - 1)", True),
    (r"Total\.covarianceP\(([^,]+),\s*([^)]+)\)", r"SUMX(ALL(), (\1 - AVERAGE(\1)) * (\2 - AVERAGE(\2))) / COUNTROWS(ALL())", True),
    (r"Total\.geometricMean\(([^)]+)\)", r"EXP(AVERAGEX(ALL(), LN(\1)))", True),
    (r"Total\.harmonicMean\(([^)]+)\)", r"COUNTROWS(ALL()) / SUMX(ALL(), 1 / \1)", True),
    (r"Total\.quartile\(([^,]+),\s*([^)]+)\)", r"PERCENTILE.INC(\1, \2 * 0.25)", True),
    (r"Total\.iqr\(([^)]+)\)", r"PERCENTILE.INC(\1, 0.75) - PERCENTILE.INC(\1, 0.25)", True),
    (r"Total\.skewness\(([^)]+)\)", r"DIVIDE(SUMX(ALL(), POWER((\1 - AVERAGE(\1)) / STDEV.S(\1), 3)), COUNTROWS(ALL()))", True),
    (r"Total\.kurtosis\(([^)]+)\)", r"DIVIDE(SUMX(ALL(), POWER((\1 - AVERAGE(\1)) / STDEV.S(\1), 4)), COUNTROWS(ALL())) - 3", True),

    # ── Time Intelligence patterns ──
    (r"Total\.ytd\(([^)]+)\)", r"TOTALYTD(SUM(\1), 'Date'[Date])", True),
    (r"Total\.mtd\(([^)]+)\)", r"TOTALMTD(SUM(\1), 'Date'[Date])", True),
    (r"Total\.qtd\(([^)]+)\)", r"TOTALQTD(SUM(\1), 'Date'[Date])", True),
    (r"Total\.priorYear\(([^)]+)\)", r"CALCULATE(SUM(\1), SAMEPERIODLASTYEAR('Date'[Date]))", True),
    (r"Total\.priorMonth\(([^)]+)\)", r"CALCULATE(SUM(\1), DATEADD('Date'[Date], -1, MONTH))", True),
    (r"Total\.priorQuarter\(([^)]+)\)", r"CALCULATE(SUM(\1), DATEADD('Date'[Date], -1, QUARTER))", True),
    (r"Total\.yoy\(([^)]+)\)", r"SUM(\1) - CALCULATE(SUM(\1), SAMEPERIODLASTYEAR('Date'[Date]))", True),
    (r"Total\.yoyPercent\(([^)]+)\)", r"DIVIDE(SUM(\1) - CALCULATE(SUM(\1), SAMEPERIODLASTYEAR('Date'[Date])), CALCULATE(SUM(\1), SAMEPERIODLASTYEAR('Date'[Date])))", True),
    (r"Total\.mom\(([^)]+)\)", r"SUM(\1) - CALCULATE(SUM(\1), DATEADD('Date'[Date], -1, MONTH))", True),
    (r"Total\.momPercent\(([^)]+)\)", r"DIVIDE(SUM(\1) - CALCULATE(SUM(\1), DATEADD('Date'[Date], -1, MONTH)), CALCULATE(SUM(\1), DATEADD('Date'[Date], -1, MONTH)))", True),
    (r"Total\.rollingAvg\(([^,]+),\s*(\d+)\)", r"AVERAGEX(DATESINPERIOD('Date'[Date], MAX('Date'[Date]), -\2, DAY), CALCULATE(SUM(\1)))", True),
    (r"Total\.rollingSum\(([^,]+),\s*(\d+)\)", r"SUMX(DATESINPERIOD('Date'[Date], MAX('Date'[Date]), -\2, DAY), CALCULATE(SUM(\1)))", True),

    # ── Conditional / logic functions ──
    (r"BirtComp\.between\(([^,]+),\s*([^,]+),\s*([^)]+)\)", r"\1 >= \2 && \1 <= \3", True),
    (r"BirtComp\.inList\(([^,]+),\s*([^)]+)\)", r"\1 IN {\2}", True),
    (r"BirtComp\.notInList\(([^,]+),\s*([^)]+)\)", r"NOT(\1 IN {\2})", True),
    (r"BirtComp\.nvl\(([^,]+),\s*([^)]+)\)", r"COALESCE(\1, \2)", True),
    (r"BirtComp\.decode\(([^,]+),\s*([^)]+)\)", r"SWITCH(\1, \2)", True),
    (r"BirtComp\.choose\(([^,]+),\s*([^)]+)\)", r"SWITCH(\1, \2)", True),
    (r"BirtComp\.isNumeric\(([^)]+)\)", r"ISNUMBER(\1)", True),
    (r"BirtComp\.isDate\(([^)]+)\)", r"NOT(ISERROR(DATEVALUE(\1)))", True),
    (r"BirtComp\.isText\(([^)]+)\)", r"ISTEXT(\1)", True),
    (r"BirtComp\.isBlank\(([^)]+)\)", r"ISBLANK(\1)", True),
    (r"BirtComp\.isError\(([^)]+)\)", r"ISERROR(\1)", True),
    (r"BirtComp\.ifError\(([^,]+),\s*([^)]+)\)", r"IFERROR(\1, \2)", True),

    # ── JavaScript standard methods ──
    (r"parseInt\(([^)]+)\)", r"INT(\1)", True),
    (r"parseFloat\(([^)]+)\)", r"VALUE(\1)", True),
    (r"String\(([^)]+)\)", r"FORMAT(\1, \"\")", True),
    (r"Number\(([^)]+)\)", r"VALUE(\1)", True),
    (r"isNaN\(([^)]+)\)", r"NOT(ISNUMBER(\1))", True),
    (r"isFinite\(([^)]+)\)", r"ISNUMBER(\1)", True),
    (r"encodeURIComponent\(([^)]+)\)", r"/* URI encoding N/A in DAX */ \1", True),

    # Null / undefined handling
    (r"null", "BLANK()", False),
    (r"undefined", "BLANK()", False),
]

# JavaScript operator → DAX operator
OPERATOR_MAP: list[tuple[str, str]] = [
    ("===", "="),
    ("!==", "<>"),
    ("==", "="),
    ("!=", "<>"),
    ("&&", "&&"),
    ("||", "||"),
    ("!", "NOT "),
]


class ExpressionConverter:
    """Converts BIRT JavaScript expressions to DAX."""

    def __init__(self):
        self._compiled_patterns: list[tuple[re.Pattern, str]] = []
        for pattern, replacement, is_regex in FUNCTION_MAP:
            if is_regex:
                self._compiled_patterns.append((re.compile(pattern), replacement))
        self.conversion_log: list[dict[str, Any]] = []

    def convert(self, expression: str, context: str = "") -> dict[str, Any]:
        """Convert a single BIRT expression to DAX.

        Args:
            expression: BIRT JavaScript expression string.
            context: Optional context (e.g., "computed_column", "highlight_rule").

        Returns:
            Dict with {original, converted, status, warnings}.
        """
        result: dict[str, Any] = {
            "original": expression,
            "converted": "",
            "status": "success",
            "warnings": [],
            "context": context,
        }

        if not expression or not expression.strip():
            result["status"] = "empty"
            return result

        converted = expression.strip()

        # Apply function mappings
        for pattern, replacement in self._compiled_patterns:
            converted = pattern.sub(replacement, converted)

        # Apply operator mappings
        for js_op, dax_op in OPERATOR_MAP:
            converted = converted.replace(js_op, dax_op)

        # Handle row[] field references → column references
        converted = re.sub(r'row\["([^"]+)"\]', r"[\1]", converted)
        converted = re.sub(r"row\['([^']+)'\]", r"[\1]", converted)
        converted = re.sub(r"row\.(\w+)", r"[\1]", converted)

        # Handle dataSetRow references
        converted = re.sub(r'dataSetRow\["([^"]+)"\]', r"[\1]", converted)

        # Handle params references → slicer/filter placeholders
        converted = re.sub(r'params\["([^"]+)"\]\.value', r"[@\1]", converted)

        # Handle JavaScript ternary → IF
        ternary_match = re.match(r"(.+?)\s*\?\s*(.+?)\s*:\s*(.+)", converted)
        if ternary_match:
            condition = ternary_match.group(1).strip()
            true_val = ternary_match.group(2).strip()
            false_val = ternary_match.group(3).strip()
            converted = f"IF({condition}, {true_val}, {false_val})"

        # Handle JavaScript if/else → IF (simple cases)
        if_match = re.match(r"if\s*\((.+?)\)\s*\{?\s*(.+?)\s*\}?\s*else\s*\{?\s*(.+?)\s*\}?$", converted, re.DOTALL)
        if if_match:
            converted = f"IF({if_match.group(1).strip()}, {if_match.group(2).strip()}, {if_match.group(3).strip()})"

        # Detect unconverted BIRT-specific patterns
        if any(marker in converted for marker in ("Total.", "BirtStr.", "BirtDateTime.", "BirtMath.", "BirtComp.")):
            result["warnings"].append("Contains unconverted BIRT functions")
            result["status"] = "partial"

        # Detect JavaScript-only constructs
        if any(kw in converted for kw in ("var ", "function ", "new ", ".prototype", "this.")):
            result["warnings"].append("Contains JavaScript constructs not convertible to DAX")
            result["status"] = "unsupported"

        result["converted"] = converted

        self.conversion_log.append(result)
        return result

    def convert_batch(
        self,
        expressions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert a batch of expressions from expressions.json."""
        results: list[dict[str, Any]] = []
        for expr in expressions:
            raw = expr.get("expression", "")
            context = expr.get("source", "")
            converted = self.convert(raw, context)
            converted["source"] = context
            converted["column_name"] = expr.get("column_name", "")
            results.append(converted)

        success = sum(1 for r in results if r["status"] == "success")
        partial = sum(1 for r in results if r["status"] == "partial")
        unsupported = sum(1 for r in results if r["status"] == "unsupported")
        logger.info(
            "Expression conversion: %d success, %d partial, %d unsupported (total: %d)",
            success, partial, unsupported, len(results),
        )
        return results

    def summary(self) -> dict[str, Any]:
        """Return conversion summary statistics."""
        statuses: dict[str, int] = {}
        for entry in self.conversion_log:
            s = entry.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        return {
            "total": len(self.conversion_log),
            "statuses": statuses,
        }
