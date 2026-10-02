#!/usr/bin/env python3
"""One measured two-surface before/after preview from the saved native FCStd.
No GUI, model changes, physical claim or print-export mesh input.
"""
import FreeCAD as App
import geometry as G

def main():
    doc=App.openDocument(str(G.ROOT/'cad/original-magnet-case.FCStd'))
    data={'native_document_sha256':G.sha256(G.ROOT/'cad/original-magnet-case.FCStd'), 'panels':[]}
    for kind,name in [('base','Base'),('lid','Lid')]:
        for state,obj in [('before',doc.getObject('Release'+name)),('after',doc.getObject(name))]:
            points,triangles=obj.Shape.tessellate(.03)
            data['panels'].append({'kind':kind,'state':state,
                'points':[[p.x,p.y,p.z] for p in points],'triangles':[list(t) for t in triangles]})
    G.write_json(G.ROOT/'.cache/preview-cad.json',data)
    App.closeDocument(doc.Name)

if __name__=='__main__': main()
