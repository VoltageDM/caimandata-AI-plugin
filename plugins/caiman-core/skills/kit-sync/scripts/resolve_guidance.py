#!/usr/bin/env python3
"""Resolve a saved guide against this session's selected folder, without writes."""
import argparse,json,sys
sys.dont_write_bytecode=True
import verify_kit as v
import plan_install as plan


def resolve(root_raw):
    root=v.root_path(root_raw);meta=root/'.caiman'
    pointer=v.strict_json(plan.source_path(meta/'active-guidance.json'))
    marker=v.strict_json(plan.source_path(meta/'workspace-id.json'))
    if pointer.get('schema')!='caiman.active-guidance.v1' or pointer.get('workspace_id')!=marker.get('id'):
        raise ValueError('Saved guidance is not bound to this workspace marker')
    ref=pointer.get('receipt',{});relative=ref.get('path','')
    if not relative.startswith('.caiman/kit-installations/') or len(relative.split('/'))!=3:
        raise ValueError('Invalid installation receipt location')
    v.portable(relative.split('/')[-1])
    # Internal metadata path is deliberately not passed to the content ownership map.
    receipt_path=plan.source_path(root/relative)
    if v.sha(receipt_path)!=ref.get('sha256'):raise ValueError('Installation receipt changed')
    receipt=v.strict_json(receipt_path)
    if receipt.get('status')!='COMPLETE_ARCHIVE_INSTALLED' or receipt.get('workspace_id')!=marker.get('id') or receipt.get('tier')!=pointer.get('tier'):
        raise ValueError('Complete workspace-bound installation receipt required')
    rel=pointer.get('guidance_relative')
    if rel!=receipt.get('guidance_relative'):raise ValueError('Guidance path differs from installation receipt')
    if rel=='.':target=root
    else:
        if not isinstance(rel,str) or not rel.startswith('.caiman/kit-versions/') or len(rel.split('/'))!=3 or rel.split('/')[-1] in ('','.','..'):
            raise ValueError('Invalid project-local companion path')
        v.portable(rel.split('/')[-1])
        target=v.root_path(root/rel)
    if target!=root and root not in target.parents:raise ValueError('Guide escapes selected workspace')
    guide='GUIDED_SETUP.py' if pointer.get('tier')=='vip' else 'GLS_GUIDED_SETUP.py' if pointer.get('tier')=='gls-plus' else None
    if not guide or v.sha(target/guide)!=receipt.get('files',{}).get(guide):raise ValueError('Selected guide bytes changed')
    return {'status':'SAVED_GUIDANCE_RESOLVED','project_root':str(root),'guidance_root':str(target),'guide':str(target/guide),
            'tier':pointer['tier'],'workspace_id':marker['id'],'receipt':relative,'path_basis':'CURRENT_SELECTED_FOLDER_PLUS_VERIFIED_RELATIVE_PATH',
            'absolute_install_paths_are_observation_only':True,'live_entitlement_verified':False,'project_changed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);a=p.parse_args()
    try:r=resolve(a.root)
    except (ValueError,OSError) as e:r={'status':'GUIDANCE_REFERENCE_NEEDS_ATTENTION','error':str(e)[:500],'project_changed':False}
    print(json.dumps(r,sort_keys=True));return 0 if r['status']=='SAVED_GUIDANCE_RESOLVED' else 2


if __name__=='__main__':raise SystemExit(main())
