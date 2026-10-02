"""Versioned, auditable wording rules. Direction is evidence, never a forecast.

Patterns apply only to a subject-bound clause supplied by news_context.
No finite dictionary covers all natural language; unsupported wording abstains.
"""
import re

VERSION = '1.0'
# category, direction, pattern, interpretation. Add phrases here, not in UI code.
RULES = [
 ('Price action','bullish',r'(?:rise[sn]?|rose|rall(?:y|ies|ied)|surg(?:e[sd]?|ing)|gain[sd]?|climb[sd]?|jump[sd]?|soar[sd]?|advance[sd]?|rebound[sd]?|recover[sy]?)', 'Reported positive price move; not a future-return prediction'),
 ('Price action','bearish',r'(?:fall[sn]?|fell|drop(?:s|ped)?|plung(?:e[sd]?|ing)|slid(?:e[sd]?)?|tumbl(?:e[sd]?)|sink[sn]?|sank|slump[sd]?|declin(?:e[sd]?)|sell off)', 'Reported negative price move; not a future-return prediction'),
 ('Earnings','bullish',r'(?:beats?|beat|tops?|topped|exceeds?|exceeded) (?:earnings |profit |revenue |sales |EPS )?(?:estimates|expectations|forecasts|consensus)', 'Results exceeded expectations'),
 ('Earnings','bearish',r'(?:miss(?:es|ed)?|falls? short of|fell short of) (?:earnings |profit |revenue |sales |EPS )?(?:estimates|expectations|forecasts|consensus)', 'Results missed expectations'),
 ('Results','bullish',r'(?:earnings|revenue|sales|profits?|EPS) (?:beat[sd]?|top[sd]?|exceed[sd]?) (?:estimates|expectations|forecasts|consensus)', 'Financial metric exceeded expectations'),
 ('Results','bearish',r'(?:earnings|revenue|sales|profits?|EPS) (?:miss(?:es|ed)?|fall short of|fell short of) (?:estimates|expectations|forecasts|consensus)', 'Financial metric missed expectations'),
 ('Growth','bullish',r'(?:revenue|sales|profits?|earnings|cash flow|orders|bookings|margins) (?:rise[sn]?|rose|grew|grow[sn]?|improve[sd]?|expand[sd]?|increase[sd]?)', 'Improving business metric; expectations may differ'),
 ('Growth','bearish',r'(?:revenue|sales|profits?|earnings|cash flow|orders|bookings|margins) (?:fall[sn]?|fell|shrank|shrink[sn]?|decline[sd]?|contract[sd]?|decrease[sd]?)', 'Deteriorating business metric; expectations may differ'),
 ('Losses','bullish',r'losses (?:narrow[sd]?|shrink[sn]?|shrank|decline[sd]?)', 'Losses decreased; company may still be unprofitable'),
 ('Losses','bearish',r'losses (?:widen[sd]?|grow[sn]?|grew|increase[sd]?)', 'Losses increased'),
 ('Guidance','bullish',r'(?:raises?|raised|lifts?|lifted|boosts?|boosted|increases?|increased) (?:annual |full.year |quarterly )?(?:profit |earnings |revenue |sales )?(?:guidance|outlook|forecast|target)', 'Raised business outlook'),
 ('Guidance','bearish',r'(?:cuts?|lower[sd]?|slashe[sd]|reduces?|reduced|withdraws?|withdrawn) (?:annual |full.year |quarterly )?(?:profit |earnings |revenue |sales )?(?:guidance|outlook|forecast|target)', 'Reduced or withdrawn business outlook'),
 ('Profitability','bullish',r'(?:reports? |reported )?(?:record profits|record earnings|record revenue|record sales|margin expansion|positive free cash flow|narrower losses|losses narrowed|a return to profit)', 'Improved business profitability'),
 ('Profitability','bearish',r'(?:reports? |reported )?(?:widening losses|wider losses|losses widened|margin compression|negative free cash flow|a profit warning|an earnings warning)', 'Deteriorating business profitability'),
 ('Balance sheet','bullish',r'(?:reduces?|reduced|pays? down|paid down) (?:its )?debt', 'Debt reduction'),
 ('Balance sheet','bearish',r'(?:files? for|filed for|enters?|entered) (?:bankruptcy|chapter 11|receivership)', 'Severe financial distress'),
 ('Credit','bearish',r'(?:defaults?|defaulted) on (?:its )?(?:debt|bonds|loans|payments)', 'Debt payment default'),
 ('Credit','bearish',r'(?:faces?|faced|reports?) (?:a )?(?:liquidity crisis|debt crisis|going.concern warning)', 'Financial solvency risk'),
 ('Capital returns','bullish',r'(?:announces?|announced|increases?|increased|raises?|raised) (?:a |its )?(?:share buyback|stock buyback|dividend|repurchase program)', 'Capital return catalyst; financing and valuation still matter'),
 ('Capital returns','bearish',r'(?:cuts?|suspends?|suspended|eliminates?|eliminated) (?:its |the )?dividend', 'Reduced shareholder distributions'),
 ('Dilution','bearish',r'(?:announces?|announced) (?:a )?(?:dilutive offering|dilutive stock sale|dilutive share issuance)', 'Explicitly dilutive capital raising'),
 ('Demand','bullish',r'(?:wins?|won|secures?|secured|lands?|landed) (?:a |an )?(?:major |new |record )?(?:contract|order|deal)', 'Reported commercial win'),
 ('Demand','bearish',r'(?:loses?|lost) (?:a |its )?(?:major |key )?(?:contract|customer|license)', 'Loss of business or operating rights'),
 ('Operations','bearish',r'(?:halts?|halted|suspends?|suspended) (?:production|operations|deliveries)', 'Operating disruption'),
 ('Operations','bullish',r'(?:resumes?|resumed|restarts?|restarted) (?:production|operations|deliveries)', 'Operating activity restored'),
 ('Product safety','bearish',r'(?:recalls?|recalled) (?:its |defective |unsafe )?(?:products|vehicles|drugs|devices)', 'Product recall risk'),
 ('Legal','bearish',r'(?:loses?|lost) (?:a |an )?(?:patent lawsuit|antitrust case|appeal)', 'Adverse legal outcome'),
 ('Legal','bullish',r'(?:wins?|won) (?:a |an )?(?:patent lawsuit|appeal|court ruling)', 'Favorable legal outcome; magnitude unknown'),
 ('Credit','bullish',r'credit rating (?:is |was )?upgraded', 'Improved reported credit assessment'),
 ('Credit','bearish',r'credit rating (?:is |was )?downgraded', 'Weaker reported credit assessment'),
 ('Regulation','bullish',r'(?:wins?|won|receives?|received|secures?|secured) (?:FDA |regulatory )approval', 'Reported regulatory clearance'),
 ('Regulation','bearish',r'(?:faces?|faced|receives?|received) (?:an? )?(?:antitrust lawsuit|regulatory fine|FDA rejection|trading ban|export ban)', 'Adverse regulatory catalyst'),
 ('Governance','bearish',r'(?:admits?|admitted|discloses?|disclosed) (?:accounting fraud|accounting irregularities|a data breach)', 'Reported governance or security failure'),
 ('Analysts','bullish',r'(?:is |was )?upgraded(?: by| to)', 'Analyst opinion improved; not a guarantee'),
 ('Analysts','bearish',r'(?:is |was )?downgraded(?: by| to)', 'Analyst opinion weakened; not a guarantee'),
 ('Unchanged','unclear',r'(?:maintains?|reiterates?|reaffirms?) (?:its )?(?:guidance|outlook|dividend)', 'No directional change established'),
 ('In-line results','unclear',r'(?:meets?|met|matches?|matched) (?:earnings |revenue )?(?:expectations|estimates|consensus)', 'Results in line with expectations'),
 ('Unchanged','unclear',r'(?:shares? |stock )?(?:unchanged|flat|mixed|range.bound|holds? steady)', 'No clear directional change'),
 ('Context dependent','unclear',r'(?:announces?|announced|plans?) (?:a |an )?(?:merger|acquisition|stock split|layoffs|restructuring|offering)', 'Context-dependent event; no automatic positive or negative assignment'),
]

MACRO_RULES = [
 ('Inflation','bullish',r'inflation (?:cools?|cooled|eases?|eased|slows?|slowed|falls?|fell|declines?|declined)', 'Easing inflation may support equities; growth context matters'),
 ('Inflation','bearish',r'inflation (?:rises?|rose|accelerates?|accelerated|surges?|surged|heats? up)', 'Rising inflation may pressure equities; growth context matters'),
 ('Macro ambiguity','unclear',r'(?:Fed|Federal Reserve) (?:cuts?|raises?|holds?) (?:interest )?rates', 'Rate decisions require expectations and economic context'),
 ('Macro ambiguity','unclear',r'(?:GDP|employment|payrolls|unemployment|Treasury yields|oil prices) (?:rise[sn]?|fall[sn]?|rose|fell|increase[sd]?|decrease[sd]?)', 'Macro direction alone does not determine equity impact'),
]
GUARD = re.compile(r"\b(?:not|no|never|denies?|denied|without|may|might|could|would|if|rumou?r|reportedly|expected to|likely to|fails? to|unlikely|won't|isn't|didn't|doesn't|don't|cannot|can't)\b|n[’']t\b|\?",re.I)
COMPILED = [(c,d,re.compile(r'\b(?:'+p+r')\b',re.I),why) for c,d,p,why in RULES]
MACRO_COMPILED = [(c,d,re.compile(r'\b(?:'+p+r')\b',re.I),why) for c,d,p,why in MACRO_RULES]

def classify_clause(text, macro=False):
    """Expect 'Stocks <predicate>' or an explicit macro clause; reject indirect subjects."""
    text=text.strip()
    if GUARD.search(text):
        return dict(direction='unclear',reason='Negated, conditional, speculative or question wording; direction withheld.',matches=[])
    hits=[]
    if macro:
        patterns=MACRO_COMPILED
        predicate=text
    else:
        subject=re.match(r"Stocks(?:['’]s)?\s+(?:(?:shares?|stock)\s+)?",text,re.I)
        if not subject:return dict(direction='unclear',reason='No unambiguous subject-linked predicate.',matches=[])
        predicate=text[subject.end():]
        patterns=COMPILED
    for category,direction,pattern,reason in patterns:
        match=pattern.match(predicate)
        if match:
            hits.append(dict(category=category,direction=direction,phrase=match.group(),reason=reason))
    directions={h['direction'] for h in hits if h['direction']!='unclear'}
    return dict(direction=next(iter(directions)) if len(directions)==1 else 'unclear',
                reason='; '.join(dict.fromkeys(h['reason'] for h in hits)) or 'No supported directional wording matched.',matches=hits)

def library_rows():
    return [dict(category=c,indicator={'bullish':'Green','bearish':'Red','unclear':'Neutral'}[d],pattern=p,interpretation=why)
            for c,d,p,why in RULES+MACRO_RULES]
