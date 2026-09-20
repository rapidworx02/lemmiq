import json
import os
import re
from urllib.parse import urlparse
import requests

URL_RE = re.compile(r"https?://[^\s<>\"\']+", re.IGNORECASE)

SYSTEM = """You are LEMMIQ Trust, a cautious verification assistant. Assess claims only from the supplied evidence. Return JSON only with keys: status, confidence, summary, reasons, sources, advice. status must be one of SUPPORTED, LIKELY_FALSE, MISLEADING, UNVERIFIED, SCAM_RISK, SUSPICIOUS. Confidence reflects evidence strength, not certainty. If evidence is weak or absent, use UNVERIFIED. Prefer primary/official sources, major news wires, regulators, universities and established fact-checkers. Never call content false merely because it sounds implausible. Detector-only image judgments are not proof."""

def extract_urls(text):
    return URL_RE.findall(text or '')

def link_risk(url):
    reasons=[]; score=0
    try:
        p=urlparse(url); host=(p.hostname or '').lower()
        if not host: return 70,['Malformed or missing domain']
        if host.count('-')>=3: score+=15; reasons.append('Domain contains many hyphens')
        if len(host)>45: score+=10; reasons.append('Unusually long domain')
        if re.match(r'^\\d+\\.\\d+\\.\\d+\\.\\d+$',host): score+=30; reasons.append('Uses raw IP address')
        if any(x in host for x in ['bit.ly','tinyurl.com','t.co','rb.gy','is.gd']): score+=15; reasons.append('Uses a URL shortener')
        if any(k in url.lower() for k in ['login','verify','secure','account','payment','wallet','claim','prize']): score+=10; reasons.append('Link contains account/payment/claim wording')
        if p.scheme!='https': score+=15; reasons.append('Link is not HTTPS')
    except Exception:
        return 70,['Could not safely parse link']
    return min(score,95),reasons

def scam_heuristics(text):
    t=(text or '').lower(); score=0; reasons=[]
    rules=[
      (25,['otp','verification code','one time password'],'Requests or discusses a verification code'),
      (20,['urgent','immediately','act now','final warning'],'Uses urgent pressure language'),
      (25,['gift card','crypto wallet','bitcoin payment'],'Requests a hard-to-reverse payment method'),
      (20,['you won','prize','lottery','claim reward'],'Unexpected prize/reward language'),
      (20,['bank account','credit card','card details','password'],'Requests sensitive financial/account information'),
      (15,['unpaid toll','parcel fee','delivery fee','customs fee'],'Common payment-demand scam theme'),
      (15,['click the link','click here','verify account'],'Pushes the recipient to open a link')]
    for pts,words,reason in rules:
        if any(w in t for w in words): score+=pts; reasons.append(reason)
    for url in extract_urls(text):
        s,r=link_risk(url); score+=min(s//4,25); reasons.extend(r[:2])
    return min(score,99),list(dict.fromkeys(reasons))

def web_search(query):
    key=os.getenv('TAVILY_API_KEY','').strip()
    if not key: return []
    try:
        r=requests.post('https://api.tavily.com/search',json={'api_key':key,'query':query,'search_depth':'advanced','max_results':6,'include_answer':False},timeout=18)
        r.raise_for_status(); data=r.json(); out=[]
        for x in data.get('results',[])[:6]:
            out.append({'title':x.get('title',''),'url':x.get('url',''),'content':(x.get('content') or '')[:1800]})
        return out
    except Exception: return []

def anthropic_assess(text,evidence,scam_score,scam_reasons):
    key=os.getenv('ANTHROPIC_API_KEY','').strip()
    if not key: return None
    from anthropic import Anthropic
    client=Anthropic(api_key=key)
    ev='\\n\\n'.join(f"SOURCE {i+1}: {x['title']}\\nURL: {x['url']}\\nEXCERPT: {x['content']}" for i,x in enumerate(evidence))
    prompt=f"MESSAGE/CLAIM:\\n{text}\\n\\nSCAM HEURISTIC SCORE: {scam_score}/100\\nREASONS: {json.dumps(scam_reasons)}\\n\\nWEB EVIDENCE:\\n{ev or 'No external evidence was available.'}\\n\\nAssess cautiously. If external evidence is weak or absent, prefer UNVERIFIED."
    m=client.messages.create(model=os.getenv('ANTHROPIC_MODEL','claude-sonnet-4-6'),max_tokens=700,temperature=0,system=SYSTEM,messages=[{'role':'user','content':prompt}])
    raw=''.join(b.text for b in m.content if getattr(b,'type','')=='text').strip()
    raw=raw.removeprefix('```json').removesuffix('```').strip()
    return json.loads(raw)

def check_text(text):
    text=(text or '').strip()
    if not text:
        return {'status':'UNVERIFIED','confidence':0,'summary':'No content to check','reasons':[],'sources':[],'advice':'Select a message containing a claim or link.'}
    scam_score,scam_reasons=scam_heuristics(text)
    evidence=web_search(text[:500])
    try: assessed=anthropic_assess(text,evidence,scam_score,scam_reasons)
    except Exception: assessed=None
    if assessed:
        assessed['confidence']=max(0,min(int(assessed.get('confidence',0)),100))
        assessed['sources']=[{'title':s.get('title',''),'url':s.get('url','')} for s in assessed.get('sources',[])[:6] if s.get('url','').startswith('http')]
        return assessed
    if scam_score>=55:
        return {'status':'SCAM_RISK','confidence':min(90,55+scam_score//3),'summary':'This message shows several common scam or phishing signals.','reasons':scam_reasons[:5],'sources':[],'advice':'Avoid opening links or sharing passwords, OTPs, banking or card details.'}
    if extract_urls(text) and scam_score>=25:
        return {'status':'SUSPICIOUS','confidence':min(75,35+scam_score//2),'summary':'This message contains a link with some risk signals.','reasons':scam_reasons[:5],'sources':[],'advice':'Verify the sender and domain independently before opening the link.'}
    return {'status':'UNVERIFIED','confidence':25,'summary':'No reliable external verification is configured on this server.','reasons':['Enable TAVILY_API_KEY for current web evidence and ANTHROPIC_API_KEY for evidence synthesis.'],'sources':[],'advice':'Treat the claim as unverified until checked against reliable sources.'}

def media_capabilities():
    return {'status':'UNVERIFIED','confidence':20,'summary':'AI-generation cannot be determined reliably from appearance alone.','reasons':['Production media verification should combine C2PA/Content Credentials provenance, original-source lookup, metadata, forensic manipulation signals and detector signals.','LEMMIQ does not treat an AI detector score as proof.'],'sources':[],'advice':'Use provenance and source verification first; treat detector-only results as advisory.'}
