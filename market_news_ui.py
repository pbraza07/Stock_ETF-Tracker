"""Responsive MarketScope news reader, source health and saved history."""
import json
import threading
from datetime import datetime, timedelta, timezone
from html import escape
from collections import Counter
from zoneinfo import ZoneInfo

import streamlit as st
from market_news import SOURCES, SOURCE_BY_ID, collect, utcnow, official_release, canonical_url
import news_archive
from news_context import story_context, story_summary, impact_html
from article_summary import configured as summaries_configured, summarize_article, SummaryUnavailable

ET=ZoneInfo('America/New_York')
_REFRESH_LOCK=threading.Lock()
LABELS={'bullish':('▲','Potentially bullish','#35ec87'),'bearish':('▼','Potentially bearish','#ff667b'),
        'mixed':('↕','Mixed evidence','#facc15'),'unclear':('↔','Direction unclear','#9daebe')}


def date_label(value):
    if not value:return 'Publication date unavailable'
    try:return datetime.fromisoformat(value).astimezone(ET).strftime('%b %d, %Y · %I:%M %p %Z')
    except ValueError:return 'Publication date unavailable'


def filtered(payload,days=7,publishers=None,direction='All',query=''):
    cutoff=utcnow()-timedelta(days=days) if days else None
    rows=[]
    for row in payload['articles'].values():
        published=row.get('published_at')
        # Undated/future-dated stories stay in archive; never pass as current reporting.
        if cutoff:
            if not published:continue
            stamp=datetime.fromisoformat(published)
            if stamp<cutoff or stamp>utcnow()+timedelta(hours=1):continue
        if publishers is not None and row['publisher'] not in publishers:continue
        if direction!='All' and story_context(row)['market']['direction']!=direction:continue
        if query and query.casefold() not in (row['title']+' '+row['excerpt']).casefold():continue
        rows.append(row)
    return sorted(rows,key=lambda r:r.get('published_at') or r['first_seen_at'],reverse=True)


def overview(rows):
    # Same headline across feeds counts once, and per-publisher counts stay visible.
    unique={r['headline_group']:r for r in rows}.values()
    counts=Counter(story_context(r)['market']['direction'] for r in unique)
    return counts,Counter(topic for r in unique for topic in r['analysis']['topics'])


@st.dialog('Market news reader',width='large')
def read_story(row):
    st.subheader(row['title'])
    st.caption(row['publisher']+' · '+date_label(row.get('published_at')))
    context=story_context(row)
    st.markdown(impact_html(context),unsafe_allow_html=True)
    if row.get('article_summary'):
        st.markdown('**Five-line article summary**')
        for line in row['article_summary']['lines']:st.write(line)
        st.caption('AI paraphrase · '+date_label(row['article_summary']['created_at'])+' · '+row['article_summary']['basis'])
    st.markdown('**Publisher feed excerpt**')
    st.text(row['excerpt'] or 'No excerpt supplied.')
    st.markdown('**MarketScope interpretation**')
    for group,items in [('Stock',context['stocks']),('Sector',context['sectors']),('Market',[context['market']])]:
        for impact in items:
            st.write(f"{group} — {impact['name']}: {impact['reason']}")
    st.caption(context['basis'])
    st.caption('Low-confidence headline/excerpt rules, not full-article analysis. Reported price moves describe the past. A potential catalyst can be priced in, offset, or affect only one sector.')
    st.markdown('**What to watch next**')
    st.write('Check the original report, its release time and the subsequent response in broad U.S. indices, Treasury yields and earnings expectations. Conflicting evidence can reverse the initial reaction.')
    st.caption('Retrieved '+date_label(row['last_seen_at'])+' · First archived '+date_label(row['first_seen_at']))
    source=SOURCE_BY_ID[row['source_id']]
    if canonical_url(row['url'],source['domains']):
        st.link_button('Read the original article ↗',row['url'],width='stretch')
    if source.get('official'):
        if st.button('Load original federal release in MarketScope',key='official_'+row['id']):
            try:
                row={**row,'official_text':official_release(row)}
                news_archive.add([row],{})
                _,message=news_archive.sync();st.caption(message)
            except Exception as exc:
                st.warning('Could not load the agency release ('+type(exc).__name__+'). Use the original link.')
        saved=row.get('official_text')
        if saved:
            st.markdown('**Original federal release text**')
            st.text(saved['text'])
            if saved['truncated']:st.caption('Long release truncated; the original link contains the complete release.')
    else:
        st.caption('Full copyrighted articles are not copied into MarketScope. The publisher link may require a subscription.')


def refresh(progress):
    if not _REFRESH_LOCK.acquire(blocking=False):
        return news_archive.load(),'Another news refresh is in progress; saved news remains available.'
    try:
        return _refresh(progress)
    finally:
        _REFRESH_LOCK.release()


def _refresh(progress):
    restored,message=news_archive.restore()
    rows,statuses=collect(progress=lambda done,total,name:progress.progress(done/total,text=f'{done}/{total} feeds processed · {name}'))
    payload=news_archive.add(rows,statuses)
    synced,sync_message=news_archive.sync()
    return payload,message+' · '+sync_message


@st.fragment(run_every='15m')
def render_market_news():
    st.subheader('Market News · Drivers & Outlook')
    st.caption('Dated reporting from financial publishers and economic agencies. Auto-checks every 15 minutes while this tab is open; all collected feed summaries are archived.')
    if not summaries_configured():
        st.info('Full-article summaries are not configured. Set OPENAI_API_KEY and MARKETSCOPE_NEWS_SUMMARY_MODEL on the server. Feed excerpts remain clearly labeled below.')
    st.markdown('<style>.news-meta{font-size:12px;color:#8ba5b6}[class*="st-key-news_summary_"] button p{display:-webkit-box;-webkit-line-clamp:unset;-webkit-box-orient:vertical;overflow:hidden;line-height:1.5;max-height:none;text-align:left}[class*="st-key-news_summary_"] button{justify-content:flex-start}.news-rule{height:1px;background:#203b4d;margin:18px 0}</style>',unsafe_allow_html=True)
    try:payload=news_archive.load()
    except (ValueError,OSError) as exc:
        st.error('The news archive could not be read. Existing data has been left untouched. '+str(exc));return
    c1,c2=st.columns([1,2])
    with c1:manual=st.button('↻ Pull all 13 news feeds now',key='refresh_market_news',width='stretch',
        help='Manually fetch every configured feed, even after a recent automatic update. New stories are archived automatically.')
    last=payload.get('updated_at')
    due=not last or (utcnow()-datetime.fromisoformat(last)).total_seconds()>=900
    # Explicit manual requests bypass the automatic freshness interval.
    # The refresh lock prevents simultaneous collectors within the app process.
    if manual or due:
        progress=st.progress(0,text='Checking saved archive and news feeds…')
        try:
            payload,message=refresh(progress)
            st.session_state['market_news_storage']=message
        except Exception as exc:
            st.warning('Refresh did not finish ('+type(exc).__name__+'). Previously saved news remains available.')
        finally:progress.empty()
    with c2:st.caption('Last collection attempt: '+(date_label(payload.get('updated_at')) if payload.get('updated_at') else 'Not yet collected'))
    st.caption(st.session_state.get('market_news_storage','Archive: '+str(news_archive.archive_path())+'. Use a persistent disk or GitHub mirroring to retain manual collections across redeploys.'))

    with st.expander('Sources, freshness & archive'):
        health=[]
        for source in SOURCES:
            status=payload['sources'].get(source['id'],{})
            health.append({'Source':source['name'],'Status':status.get('status','NOT CHECKED'),
                'Last successful fetch':date_label(status.get('last_success_at')) if status.get('last_success_at') else 'None',
                'Latest attempt':date_label(status.get('attempted_at')) if status.get('attempted_at') else 'None',
                'Items in latest feed':status.get('count',0),'Error':status.get('error',''),'Feed':source['url']})
        st.dataframe(health,hide_index=True,width='stretch')
        st.caption('A successful fetch does not mean the publisher has released new news. Unavailable sources do not erase archived articles. Scheduled collection is provided by the included GitHub workflow; it is not running until deployed.')
        st.download_button('Download complete saved news archive',json.dumps(payload,ensure_ascii=False,indent=2),
            file_name='MarketScope_Market_News_Archive.json',mime='application/json',width='stretch')

    if not payload['articles']:
        st.warning('No news has been collected yet. Review source status above. No sample or invented news is shown.');return
    options={'Last 24 hours':1,'Last 7 days':7,'Last 30 days':30,'All archived news':None}
    a,b=st.columns(2)
    with a:period=st.selectbox('News period',list(options),index=1,key='news_period')
    with b:direction=st.selectbox('Potential overall-market effect',['All','bullish','bearish','mixed','unclear'],key='news_direction')
    publishers=sorted({r['publisher'] for r in payload['articles'].values()})
    chosen=st.multiselect('Sources',publishers,default=publishers,key='news_publishers')
    query=st.text_input('Search headlines and excerpts',key='news_query')
    rows=filtered(payload,options[period],chosen,direction,query)
    recent=filtered(payload,7)
    counts,topics=overview(recent)
    st.markdown('**What is driving the discussion? · Last 7 days**')
    st.write(' · '.join(f'{topic}: {n} stories' for topic,n in topics.most_common(5)) or 'Insufficient dated reporting.')
    st.caption(f"Distinct headlines: ▲ {counts['bullish']} potentially bullish · ▼ {counts['bearish']} potentially bearish · ↕ {counts['mixed']} mixed · ↔ {counts['unclear']} unclear. These counts are not probabilities or a market forecast; coverage and syndicated stories can skew them.")
    with st.expander('Where might the market head? Conditional scenarios'):
        st.write('Upside case: improving earnings and easing financing pressure could support equities if expectations are not already priced in.')
        st.write('Downside case: weaker earnings, tighter financial conditions or escalating shocks could pressure equities.')
        st.write('Mixed case: offsetting growth, inflation and valuation signals can produce volatile or range-bound markets. News alone cannot establish the next market move.')
        st.caption('These are standing scenarios, not forecasts inferred from today’s headlines. Labels use transparent headline rules with LOW confidence, not an investment recommendation.')
    st.caption(f'{len(rows):,} matching stories · {len(payload["articles"]):,} archived. Click a story summary to open its reader. Full-article summaries contain five concise sentences, one per line; lines may wrap on phones. Stories without a completed summary are marked as feed excerpts.')
    if not rows:st.info('No stories match these filters. Undated stories can be found under All archived news.');return
    pages=max(1,(len(rows)+19)//20)
    if st.session_state.get('news_page',1)>pages:st.session_state['news_page']=1
    page=st.number_input('Page',min_value=1,max_value=pages,value=1,step=1,key='news_page')
    for row in rows[(page-1)*20:page*20]:
        context=story_context(row)
        st.markdown(f'<div class="news-meta">{escape(row["publisher"])} · {escape(date_label(row.get("published_at")))}</div>'+impact_html(context),unsafe_allow_html=True)
        st.markdown('**'+escape(row['title']).replace('$',r'\$')+'**')
        completed=row.get('article_summary')
        st.caption('Full-article summary · AI paraphrase' if completed else 'Feed excerpt only — full-article summary not yet available')
        with st.container(key='news_summary_'+row['id']):
            if st.button('\n\n'.join(completed['lines']) if completed else story_summary(row),key='news_read_'+row['id'],width='stretch',help='Open the story reader. A full-article summary uses five concise lines; the status identifies feed-only previews.'):
                read_story(row)
        if not completed and summaries_configured():
            if st.button('Read full article & summarize in five lines',key='summarize_'+row['id'],width='stretch'):
                try:
                    with st.spinner('Reading the original article and summarizing its full accessible body…'):
                        summary=summarize_article(row)
                        news_archive.add([{**row,'article_summary':summary}],{})
                        news_archive.sync()
                    st.rerun(scope='fragment')
                except (SummaryUnavailable,ValueError,OSError) as exc:
                    st.warning('Full-article summary unavailable: '+str(exc))
                except Exception:
                    st.warning('The article could not be read. Use the original source; no summary was substituted.')
        st.link_button('Original source ↗',row['url'])
        st.markdown('<div class="news-rule"></div>',unsafe_allow_html=True)
