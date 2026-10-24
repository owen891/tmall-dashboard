"""Parse actual HTML relationships; --root permits unchanged baseline/rollback tests."""
import argparse, collections, json, sys
from pathlib import Path
from html.parser import HTMLParser
class Tree(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True); self.nodes=[]; self.stack=[]; self.feed(text)
    def handle_starttag(self, tag, attrs):
        node=dict(tag=tag, attrs=dict(attrs), ancestors=self.stack[:], i=len(self.nodes)); self.nodes.append(node)
        if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}: self.stack.append(node['i'])
    def handle_endtag(self, tag):
        for j in range(len(self.stack)-1,-1,-1):
            if self.nodes[self.stack[j]]['tag']==tag: self.stack=self.stack[:j]; break
    def find(self, attr=None, value=None, cls=None):
        found=[n for n in self.nodes if (attr is None or (attr in n['attrs'] and (value is None or n['attrs'][attr]==value))) and (cls is None or cls in n['attrs'].get('class','').split())]
        assert len(found)==1, f'unique node {attr}={value} class={cls}: {len(found)}'; return found[0]
def within(child,parent): return parent['i'] in child['ancestors']
def signature(tree):
    hooks=collections.Counter((n['tag'],k,v) for n in tree.nodes for k,v in n['attrs'].items() if k.startswith('data-') or k=='name')
    ids=collections.Counter(n['attrs']['id'] for n in tree.nodes if 'id' in n['attrs'])
    controls=collections.Counter(n['tag'] for n in tree.nodes if n['tag'] in {'button','input','select','option','form','dialog','template'})
    scripts=[n['attrs'].get('src') for n in tree.nodes if n['tag']=='script']
    return dict(hooks=sorted([list(k)+[v] for k,v in hooks.items()]),ids=dict(ids),controls=dict(controls),scripts=scripts)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=ap.parse_args()
    trees={p:Tree((args.root/f'frontend/ui_demo/pages/{p}.html').read_text(encoding='utf8')) for p in ['products','promotion','settings']}
    frozen=json.loads((Path(__file__).parent/'fixtures/macos_structure_hooks.json').read_text(encoding='utf8'))
    tests=[]
    def test(name):
        def register(fn): tests.append((name,fn));return fn
        return register
    @test('products list precedes complete matrix and analysis')
    def product_order():
        t=trees['products']; table=t.find(attr='id',value='products-list');analysis=t.find(attr='id',value='products-analysis');matrix=t.find(attr='data-product-matrix-board')
        assert table['i']<analysis['i']<matrix['i']
        assert within(t.find(attr='id',value='productsListTitle'),table)
    @test('products column controls inside list not title; jump targets resolve')
    def product_tools():
        t=trees['products'];control=t.find(attr='data-products-columns-open');assert within(control,t.find(attr='id',value='products-list'))
        assert not within(control,t.find(cls='ui-page-header'))
        for target in ['products-list','products-analysis']: assert t.find(attr='href',value='#'+target)
    @test('promotion KPI before diagnosis inside overview')
    def promotion_order():
        t=trees['promotion'];kpi=t.find(attr='aria-label',value='推广核心指标');diagnosis=t.find(cls='promotion-decision-card');panel=t.find(attr='data-promotion-view-panel',value='overview')
        assert kpi['i']<diagnosis['i'];assert within(kpi,panel) and within(diagnosis,panel)
    @test('promotion range and unique source share global context')
    def promotion_context():
        t=trees['promotion'];context=t.find(cls='promotion-workspace-context')
        for hook in ['data-promotion-range','data-promotion-source-base','data-promotion-source-note']: assert within(t.find(attr=hook),context)
        for panel in ['overview','plans','products']: assert not within(context,t.find(attr='data-promotion-view-panel',value=panel))
    @test('settings navigation and main are workspace siblings')
    def settings_structure():
        t=trees['settings'];aside=t.find(cls='settings-navigation');main=t.find(cls='settings-main');workspace=t.find(cls='settings-workspace')
        assert aside['ancestors'][-1]==main['ancestors'][-1]==workspace['i'];assert aside['i']<main['i']
        for cls in ['settings-hero','settings-tabs']: assert within(t.find(cls=cls),aside)
        assert within(t.find(attr='data-settings-form'),main)
    for page in trees:
        @test(page+' original data/name hooks, controls, scripts and IDs preserved')
        def preservation(page=page):
            now=signature(trees[page]);old=frozen[page]
            for key in ['hooks','controls','scripts']: assert now[key]==old[key], key+' changed'
            assert all(now['ids'].get(k)==v for k,v in old['ids'].items()), 'original IDs changed'
            assert all(v==1 for v in now['ids'].values()), 'duplicate IDs'
    @test('three page adapters load after shared theme and are desktop scoped')
    def styles():
        for page,t in trees.items():
            links=[n['attrs'].get('href','') for n in t.nodes if n['tag']=='link' and n['attrs'].get('rel')=='stylesheet']
            assert 'macos-content.css' in links[-2] and page+'-workspace.css' in links[-1]
            css=(args.root/f'frontend/ui_demo/assets/themes/{page}-workspace.css').read_text(encoding='utf8');assert '@media (min-width: 960px)' in css
            assert '[hidden]' not in css
            if page=='promotion': assert 'grid-row: auto;' in css, 'legacy explicit grid rows must be reset'
    failures=0
    for name,fn in tests:
        try: fn();print('PASS '+name)
        except (AssertionError,FileNotFoundError,IndexError) as e: failures+=1;print('FAIL '+name+': '+str(e))
    print(f'RESULT {len(tests)-failures}/{len(tests)} passed; {failures} failed');return bool(failures)
if __name__=='__main__':sys.exit(main())
