import re
import subprocess
from streamlit.testing.v1 import AppTest
from economic_calendar import calendar_panel


def test_calendar_panel_mounts_once():
    app=AppTest.from_string('from economic_calendar import render_economic_calendar\nrender_economic_calendar()').run()
    assert not app.exception
    assert len(app.get('iframe'))==1
    assert 'showCalendar' in app.get('iframe')[0].proto.srcdoc


def test_browser_switch_replaces_frame_without_server_and_preserves_crop():
    script=re.search(r'<script>(.*?)</script>',calendar_panel(),re.S).group(1)
    harness=r'''
const assert=require('node:assert/strict');
const nodes={};
for(const id of ['switch','title','description','calendar','source','crop','top','bottom']){
 nodes[id]={value:id==='top'?'250':'65',listeners:{},setAttribute(){},
 addEventListener(type,fn){this.listeners[type]=fn},replaceChildren(child){this.children=[child]}};
}
global.document={getElementById:id=>nodes[id],createElement:tag=>({tag})};
'''
    checks=r'''
assert.match(nodes.calendar.children[0].srcdoc,/sslecal2/);
for(let i=0;i<5;i++){
 const previous=nodes.calendar.children[0];
 nodes.switch.listeners.click();
 assert.equal(nodes.switch.textContent,'← Back to Economic Calendar');
 assert.match(nodes.calendar.children[0].srcdoc,/earnings-calendar/);
 assert.notEqual(previous,nodes.calendar.children[0]);
 nodes.top.value='100';nodes.top.listeners.change();
 assert.match(nodes.calendar.children[0].srcdoc,/top:-100px/);
 nodes.switch.listeners.click();
 assert.equal(nodes.calendar.children.length,1);
 assert.match(nodes.calendar.children[0].srcdoc,/sslecal2/);
 assert.doesNotMatch(nodes.calendar.children[0].srcdoc,/earnings-calendar/);
 assert.equal(nodes.crop.hidden,true);
}
showCalendar('economic');showCalendar('economic');
assert.match(nodes.calendar.children[0].srcdoc,/sslecal2/);
'''
    subprocess.run(['node','-e',harness+script+checks],check=True,capture_output=True,text=True)
