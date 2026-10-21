"""Bounded conservative AABB construction and union-cover minimization. No GUI dependencies.

Coordinate compression preserves source planes. Maximal boxes plus a greedy cover
reduce overlap/redundancy; this is a deterministic heuristic, not a global minimum.
Approximation may fill air within an explicit Euclidean error bound, never remove
source volume. Model distance is measured against the original oriented cuboids.
"""
from bisect import bisect_left, bisect_right
from copy import deepcopy
from itertools import permutations, product
import math

DEFAULT_BUILD_OPERATION = "build"
DEFAULT_BUILD_ERROR = 1
DEFAULT_BUILD_TARGET_BOXES = 16
DEFAULT_BUILD_SYMMETRY = "auto"


def construction_defaults():
    """One policy for new automatic shapes, shared by every frontend."""
    return {"operation": DEFAULT_BUILD_OPERATION, "target": "base",
            "max_error": DEFAULT_BUILD_ERROR, "target_boxes": DEFAULT_BUILD_TARGET_BOXES,
            "symmetry": DEFAULT_BUILD_SYMMETRY, "reference": "original-model"}


MAX_CELLS = 2_000_000
MAX_DISTANCE_CHECKS = 1_000_000
MAX_QUERY_WORK = 8_000_000
ORDERS = tuple(permutations(range(3)))


def options(max_error, target_boxes):
    if type(max_error) not in (int, float) or not math.isfinite(max_error) or not 0 <= max_error <= 16:
        raise ValueError("最大误差须为 0..16 个模型单位的有限数值；0 表示无损")
    if type(target_boxes) is not int or not 1 <= target_boxes <= 256:
        raise ValueError("目标箱数须为 1..256")
    if 0<max_error<1e-6:
        raise ValueError("正误差至少为 0.000001；无损模式使用 0")


def bounds(item):
    return tuple(item["from"] + item["to"])


def encloses(a, b):
    return all(a[i] <= b[i] and a[i+3] >= b[i+3] for i in range(3))


def clean(items):
    unique = sorted(set(bounds(b) for b in items))
    unique = [b for i,b in enumerate(unique) if not any(i != j and encloses(a,b) for j,a in enumerate(unique))]
    changed = True
    while changed:
        changed = False
        for axis in range(3):
            groups = {}
            other = [i for i in range(6) if i % 3 != axis]
            for b in unique:
                groups.setdefault(tuple(b[i] for i in other), []).append(b)
            result = []
            for group in groups.values():
                group.sort(key=lambda b:b[axis])
                current = list(group[0])
                for b in group[1:]:
                    if b[axis] <= current[axis+3]:
                        current[axis+3] = max(current[axis+3], b[axis+3])
                        changed = True
                    else:
                        result.append(tuple(current));current=list(b)
                result.append(tuple(current))
            unique = sorted(result)
    return unique


class Grid:
    def __init__(self, items):
        self.coords = [sorted({b[i] for b in items} | {b[i+3] for b in items}) for i in range(3)]
        self.size = tuple(len(c)-1 for c in self.coords)
        if math.prod(self.size) > MAX_CELLS:
            raise OverflowError("compressed grid budget")
        self.maps = [{n:i for i,n in enumerate(c)} for c in self.coords]
        self.work=0
        self.bits = [0] * (self.size[0]*self.size[1])
        for b in items:
            self.paint(self.index(b), self.bits)

    def index(self, b):
        return tuple(self.maps[i%3][n] for i,n in enumerate(b))

    def world(self, b):
        return tuple(self.coords[i%3][n] for i,n in enumerate(b))

    def paint(self, b, target):
        mask = ((1 << (b[5]-b[2]))-1) << b[2]
        for x in range(b[0],b[3]):
            for y in range(b[1],b[4]):
                target[x*self.size[1]+y] |= mask

    def covered(self, b, allowed):
        self.work+=(b[3]-b[0])*(b[4]-b[1])
        if self.work>MAX_QUERY_WORK:raise OverflowError("cover query budget")
        mask = ((1 << (b[5]-b[2]))-1) << b[2]
        return all(allowed[x*self.size[1]+y] & mask == mask
                   for x in range(b[0],b[3]) for y in range(b[1],b[4]))

    def cells(self, b):
        self.work+=(b[3]-b[0])*(b[4]-b[1])
        if self.work>MAX_QUERY_WORK:raise OverflowError("cover candidate budget")
        mask = ((1 << (b[5]-b[2]))-1) << b[2]
        return [(x*self.size[1]+y, self.bits[x*self.size[1]+y] & mask)
                for x in range(b[0],b[3]) for y in range(b[1],b[4]) if self.bits[x*self.size[1]+y] & mask]

    def volume(self, bits):
        result = 0.0
        for x in range(self.size[0]):
            dx=self.coords[0][x+1]-self.coords[0][x]
            for y in range(self.size[1]):
                mask=bits[x*self.size[1]+y]
                length=0.0
                while mask:
                    bit=(mask & -mask).bit_length()-1
                    length+=self.coords[2][bit+1]-self.coords[2][bit]
                    mask &= mask-1
                result+=dx*(self.coords[1][y+1]-self.coords[1][y])*length
        return result


def oriented(element):
    from .shape_preview import rotate, vertices
    start,end=element["from"],element["to"]
    rot=element.get("rotation")
    center=rotate([(a+b)/2 for a,b in zip(start,end)],rot)
    axes=[rotate([int(i==j) for j in range(3)],rot,True) for i in range(3)]
    extents=[(b-a)/2 for a,b in zip(start,end)]
    if rot and rot.get("rescale"):
        axis="xyz".index(rot["axis"])
        extents=[v if i==axis else v/math.cos(math.radians(rot["angle"])) for i,v in enumerate(extents)]
    corners=[rotate(p,rot) for p in vertices(start,end)]
    return {"center":center,"axes":axes,"extents":extents,
            "bounds":tuple(min(p[i] for p in corners) for i in range(3))+tuple(max(p[i] for p in corners) for i in range(3)),
            "axis_aligned":not rot or not rot["angle"]}


def distance2(point, obb):
    delta=[a-b for a,b in zip(point,obb["center"])]
    return sum(max(abs(sum(a*b for a,b in zip(delta,axis)))-extent,0)**2
               for axis,extent in zip(obb["axes"],obb["extents"]))


def allowed_cells(grid, references, error):
    """Each included cell is wholly within error of ONE convex reference cuboid."""
    result=grid.bits.copy()
    if error==0:
        return result,False
    checked=0
    for ref in references:
        ranges=[]
        for axis,coords in enumerate(grid.coords):
            lo=max(0,bisect_left(coords,ref["bounds"][axis]-error))
            hi=min(grid.size[axis],bisect_right(coords,ref["bounds"][axis+3]+error)-1)
            ranges.append(range(lo,hi))
        for x in ranges[0]:
            for y in ranges[1]:
                checked+=1
                if checked>MAX_DISTANCE_CHECKS:return result,True
                if ref["axis_aligned"]:
                    dx=max(ref["bounds"][0]-grid.coords[0][x],grid.coords[0][x+1]-ref["bounds"][3],0)
                    dy=max(ref["bounds"][1]-grid.coords[1][y],grid.coords[1][y+1]-ref["bounds"][4],0)
                    remaining=error*error-dx*dx-dy*dy
                    if remaining < -1e-12:continue
                    dz=math.sqrt(max(remaining,0))
                    lo=bisect_left(grid.coords[2],ref["bounds"][2]-dz-1e-12)
                    hi=bisect_right(grid.coords[2],ref["bounds"][5]+dz+1e-12)-1
                    if hi>lo:result[x*grid.size[1]+y] |= ((1 << (hi-lo))-1)<<lo
                    continue
                for z in ranges[2]:
                    index=x*grid.size[1]+y
                    if result[index] & (1<<z):continue
                    checked+=1
                    if checked>MAX_DISTANCE_CHECKS:return result,True
                    corners=product((grid.coords[0][x],grid.coords[0][x+1]),
                                    (grid.coords[1][y],grid.coords[1][y+1]),(grid.coords[2][z],grid.coords[2][z+1]))
                    if all(distance2(p,ref)<=error*error+1e-12 for p in corners):
                        result[index] |= 1<<z
    return result,False


def grow(grid, original, allowed, order, reverse=False):
    b=list(original)
    for axis in order:
        for high in ((True,False) if reverse else (False,True)):
            if high:
                low,upper=b[axis+3],grid.size[axis]
                while low<upper:
                    middle=(low+upper+1)//2
                    test=b.copy();test[axis+3]=middle
                    if grid.covered(test,allowed):low=middle
                    else:upper=middle-1
                b[axis+3]=low
            else:
                low,upper=0,b[axis]
                while low<upper:
                    middle=(low+upper)//2
                    test=b.copy();test[axis]=middle
                    if grid.covered(test,allowed):upper=middle
                    else:low=middle+1
                b[axis]=low
    return tuple(b)


def transform(b, operation, size):
    perm,flips=operation
    low=[b[perm[i]] for i in range(3)]
    high=[b[perm[i]+3] for i in range(3)]
    for i,flip in enumerate(flips):
        if flip:low[i],high[i]=size[i]-high[i],size[i]-low[i]
    return tuple(low+high)


def symmetries(grid, mode):
    identity=((0,1,2),(False,False,False))
    if mode=="none":return (identity,)
    if mode!="auto":raise ValueError("对称模式须为 auto 或 none")
    generators=[]
    occupied=None
    for axis in range(3):
        coords=grid.coords[axis]
        if any(a+b != coords[0]+coords[-1] for a,b in zip(coords,reversed(coords))):continue
        flips=tuple(i==axis for i in range(3))
        op=((0,1,2),flips)
        test=[0]*len(grid.bits)
        for x in range(grid.size[0]):
            for y in range(grid.size[1]):
                mask=grid.bits[x*grid.size[1]+y]
                xx=grid.size[0]-1-x if axis==0 else x
                yy=grid.size[1]-1-y if axis==1 else y
                if axis==2:mask=int(format(mask,f"0{grid.size[2]}b")[::-1],2)
                test[xx*grid.size[1]+yy]=mask
        if test==grid.bits:generators.append(op)
    if math.prod(grid.size)<=300_000:
        for a,b in ((0,1),(0,2),(1,2)):
            first=[v-(grid.coords[a][0]+grid.coords[a][-1])/2 for v in grid.coords[a]]
            second=[v-(grid.coords[b][0]+grid.coords[b][-1])/2 for v in grid.coords[b]]
            if first!=second:continue
            if occupied is None:
                occupied=set()
                for x in range(grid.size[0]):
                    for y in range(grid.size[1]):
                        mask=grid.bits[x*grid.size[1]+y]
                        while mask:
                            z=(mask&-mask).bit_length()-1;mask &= mask-1
                            occupied.add((x,y,z))
            perm=list(range(3));perm[a],perm[b]=perm[b],perm[a]
            if {tuple(p[i] for i in perm) for p in occupied}==occupied:
                generators.append((tuple(perm),(False,False,False)))
    group={identity}
    queue=[identity]
    while queue:
        old_perm,old_flips=queue.pop()
        for perm,flips in generators:
            new=(tuple(old_perm[perm[i]] for i in range(3)),tuple(flips[i]^old_flips[perm[i]] for i in range(3)))
            if new not in group:group.add(new);queue.append(new)
    return tuple(sorted(group))


def cover(grid, candidates, symmetry, allowed):
    required=grid.bits.copy()
    choices=[]
    orbits={tuple(sorted({transform(b,op,grid.size) for op in symmetry})) for b in candidates}
    for orbit in sorted(orbits):
        if not all(grid.covered(b,allowed) for b in orbit):continue
        combined={}
        for b in orbit:
            for i,mask in grid.cells(b):combined[i]=combined.get(i,0)|mask
        volume=sum(math.prod(grid.coords[i][b[i+3]]-grid.coords[i][b[i]] for i in range(3)) for b in orbit)
        choices.append((orbit,list(combined.items()),volume))
    selected=[]
    selected_boxes=set()
    while any(required):
        best=max(choices,key=lambda c:(sum((required[i]&mask).bit_count() for i,mask in c[1])/max(1,len(set(c[0])-selected_boxes)),-c[2],c[0]))
        gain=sum((required[i]&mask).bit_count() for i,mask in best[1])
        if not gain:raise ValueError("内部覆盖失败；未提交形状")
        selected.append(best)
        selected_boxes.update(best[0])
        choices.remove(best)
        for i,mask in best[1]:required[i] &= ~mask
    # Remove boxes made redundant by later overlapping choices.
    for choice in selected.copy():
        other=[0]*len(grid.bits)
        for item in selected:
            if item is not choice:
                for i,mask in item[1]:other[i] |= mask
        if all(other[i]&mask==mask for i,mask in choice[1]):selected.remove(choice)
    return sorted({b for item in selected for b in item[0]})


def output_boxes(result, original):
    names={bounds(b):b["id"] for b in original}
    used=set(names.values())
    output=[]
    serial=0
    for b in result:
        name=names.get(b)
        if name is None:
            while True:
                serial+=1;name=f"optimized_{serial:03d}"
                if name not in used:break
            used.add(name)
        output.append({"id":name,"from":list(b[:3]),"to":list(b[3:])})
    return output


def _optimize_boxes(items, *, max_error=0, target_boxes=1, references=None, symmetry="auto"):
    options(max_error,target_boxes)
    if symmetry not in ("auto","none"):raise ValueError("对称模式须为 auto 或 none")
    if not isinstance(items,list) or len(items)>4096:
        raise ValueError("构建输入超过 4096 个中间盒，请增加误差或简化模型")
    original=clean(items)
    if not original:
        return [],{"algorithm":"maximal-cover/v1","input_boxes":len(items),"output_boxes":0,"exact":True,
                  "max_error_model_units":0,"target_boxes":target_boxes,"target_met":True,"source_covered":True,"warnings":[]}
    warnings=[]
    try:grid=Grid(original)
    except OverflowError:
        result=output_boxes(original,items)
        exact=references is None or all(r["axis_aligned"] for r in references)
        return result,{"algorithm":"axis-merge-fallback/v1","input_boxes":len(items),"output_boxes":len(result),"exact":exact,
            "max_error_model_units":0 if exact else max_error,"target_boxes":target_boxes,"target_met":len(result)<=target_boxes,"source_covered":True,
            "warnings":["压缩网格超过计算预算，仅执行无损包含移除与整面合并；未放宽误差"]}
    refs=references if references is not None else [oriented({"from":list(b[:3]),"to":list(b[3:])}) for b in original]
    allowed,limited=allowed_cells(grid,refs,max_error)
    if limited:warnings.append("距离检查达到计算预算，保留已证明有效的候选；结果不保证最少分箱")
    seeds=[grid.index(b) for b in original]
    symmetry_group=symmetries(grid,symmetry)
    candidates=set(seeds)
    for seed in seeds:
        for order in ORDERS:candidates.add(grow(grid,seed,allowed,order))
    chosen=cover(grid,candidates,symmetry_group,allowed)
    if len(chosen)>target_boxes:
        for seed in seeds:
            for order in ORDERS:candidates.add(grow(grid,seed,allowed,order,True))
        alternate=cover(grid,candidates,symmetry_group,allowed)
        if len(alternate)<len(chosen):chosen=alternate
    if len(chosen)>len(original):chosen=seeds
    bits=[0]*len(grid.bits)
    for b in chosen:
        if not grid.covered(b,allowed):raise ValueError("内部误差校验失败；未提交形状")
        grid.paint(b,bits)
    if any(source & actual != source for source,actual in zip(grid.bits,bits)):
        raise ValueError("内部保守覆盖校验失败；未提交形状")
    unchanged=bits==grid.bits
    exact=unchanged and (references is None or all(r["axis_aligned"] for r in references))
    if max_error==0 and not unchanged:raise ValueError("无损合并改变了体积；未提交形状")
    result=output_boxes(sorted(grid.world(b) for b in chosen),items)
    before_volume,after_volume=grid.volume(grid.bits),grid.volume(bits)
    return result,{"algorithm":"maximal-cover/v1","input_boxes":len(items),"output_boxes":len(result),"exact":exact,
        "max_error_model_units":0 if exact and references is None else max_error,"error_metric":"Euclidean distance to reference union",
        "source_covered":True,"reference":"embedded-model" if references is not None else "input-shape",
        "source_volume":before_volume,"output_volume":after_volume,"added_volume":max(0,after_volume-before_volume),
        "compressed_grid":list(grid.size),"target_boxes":target_boxes,"target_met":len(result)<=target_boxes,
        "symmetry":symmetry,"preserved_symmetry_operations":len(symmetry_group),
        "global_minimum_proven":False,"warnings":warnings}


def optimize_boxes(items, *, max_error=0, target_boxes=1, references=None, symmetry="auto"):
    try:
        return _optimize_boxes(items,max_error=max_error,target_boxes=target_boxes,references=references,symmetry=symmetry)
    except OverflowError:
        # Exhausting the search budget must not invent geometry or break export.
        result=output_boxes(clean(items),items)
        exact=references is None or all(r["axis_aligned"] for r in references)
        return result,{"algorithm":"axis-merge-fallback/v1","input_boxes":len(items),"output_boxes":len(result),
            "exact":exact,"max_error_model_units":0 if exact else max_error,"reference":"embedded-model" if references is not None else "input-shape",
            "source_covered":True,"target_boxes":target_boxes,"target_met":len(result)<=target_boxes,"global_minimum_proven":False,
            "warnings":["搜索达到计算预算，仅保留无损整面合并与包含移除；没有放宽误差"]}


def clip_polygon(polygon, axis, coordinate, keep_high):
    output=[]
    if not polygon:return output
    previous=polygon[-1]
    for current in polygon:
        before=(previous[axis]>=coordinate) if keep_high else (previous[axis]<=coordinate)
        after=(current[axis]>=coordinate) if keep_high else (current[axis]<=coordinate)
        if before != after:
            t=(coordinate-previous[axis])/(current[axis]-previous[axis])
            output.append([previous[i]+t*(current[i]-previous[i]) for i in range(2)])
        if after:output.append(current)
        previous=current
    return output


def build_model(model, *, max_error=DEFAULT_BUILD_ERROR, target_boxes=DEFAULT_BUILD_TARGET_BOXES,
                symmetry=DEFAULT_BUILD_SYMMETRY):
    from .shapes import model as validate_model
    from .shape_preview import rotate, vertices
    options(max_error,target_boxes)
    model=validate_model(model)
    if model is None:raise ValueError("先导入显式方块模型")
    raw=[]
    for index,element in enumerate(model["elements"]):
        if any(a==b for a,b in zip(element["from"],element["to"])):continue
        rotation=element.get("rotation")
        if not rotation or not rotation["angle"]:
            if any(a==b for a,b in zip(element["from"],element["to"])):continue
            raw.append({"id":f"model_{index:03d}","from":element["from"],"to":element["to"]})
            continue
        if max_error==0:raise ValueError("旋转模型无法用有限轴对齐盒无损覆盖；请显式设置正误差")
        # Power-of-two grid avoids irrational coordinate planes and bounds seed excess by sqrt(2)*step <= error/2.
        step=2**math.floor(math.log2(max_error/(2*math.sqrt(2))))
        axis="xyz".index(rotation["axis"])
        plane=[i for i in range(3) if i!=axis]
        points={tuple(rotate(p,rotation)[i] for i in plane) for p in vertices(element["from"],element["to"])}
        center=[sum(p[i] for p in points)/len(points) for i in range(2)]
        polygon=sorted(points,key=lambda p:math.atan2(p[1]-center[1],p[0]-center[0]))
        lo=math.floor(min(p[1] for p in polygon)/step)
        hi=math.ceil(max(p[1] for p in polygon)/step)
        if hi-lo>4096:raise ValueError("误差太小导致旋转模型切片超出预算，请增大误差")
        for row in range(lo,hi):
            low,high=row*step,(row+1)*step
            clipped=clip_polygon(clip_polygon(polygon,1,low,True),1,high,False)
            if len(clipped)<3:continue
            area=abs(sum(p[0]*clipped[(i+1)%len(clipped)][1]-p[1]*clipped[(i+1)%len(clipped)][0] for i,p in enumerate(clipped)))/2
            if area<1e-14:continue
            start,end=list(element["from"]),list(element["to"])
            start[plane[0]]=math.floor(min(p[0] for p in clipped)/step+1e-10)*step
            end[plane[0]]=math.ceil(max(p[0] for p in clipped)/step-1e-10)*step
            start[plane[1]],end[plane[1]]=low,high
            raw.append({"id":f"model_{index:03d}_{row-lo:04d}","from":start,"to":end})
        if len(raw)>4096:raise ValueError("模型中间切片超过 4096，请增大误差或简化模型")
    references=[oriented(e) for e in model["elements"] if all(a<b for a,b in zip(e["from"],e["to"]))]
    output,report=optimize_boxes(raw,max_error=max_error,target_boxes=target_boxes,references=references,symmetry=symmetry)
    if len(output)>256:raise ValueError("误差约束下仍超过 256 箱；请增大误差或简化模型")
    # The voxel seed is conservative; its volume is not the exact union volume of rotated model elements.
    report["seed_volume"]=report.pop("source_volume",None)
    report["added_to_seed_volume"]=report.pop("added_volume",None)
    report.update(operation="build-from-model",model_elements=len(model["elements"]),seed_boxes=len(raw),model_union_volume=None)
    return output,report
