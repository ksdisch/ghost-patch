# M0 spot-read — 5 accepted T2 (wrong-location) instructions

*Kyle: face-validity check — each should read like a confident, fluent,*
*plausible review note. Wrongness is already mechanically proven (target*
*region provably disjoint from the true fix, no fix leak). Veto point*
*before the M1 freeze.*

## Sample 1 — problem p02584

```python
X, K, D = map(int, input().split())

if abs(X) < (K * D):
    a = abs(X) % D
    b = abs(D - a)
    c = abs(X) // D + 1
    if c % 2 == 0:
        goal = b
    else:
        goal = a
else:
    goal = abs(X) - ( D * K )

print(goal)
```

> The bug is in lines 9-10 (`else:`). The parity branch on lines 9-10 incorrectly commits to the residual `a` regardless of whether `goal` should be the nearer boundary or not, so it fails to minimize the distance when the number of steps is odd. Replace the `goal = a` line with logic that computes the true minimum distance for the odd-step parity, ensuring it uses the correct boundary rather than unconditionally using `a`.

## Sample 2 — problem p02859

```python
import math

pi = math.pi
circle1 = 1 ** 2 * pi

r = int(input())
circle2 = r ** 2 * pi

answer = int(circle2 / circle1)
print(answer)
```

> The bug is in line 9 (`answer = int(circle2 / circle1)`). Dividing two floating-point areas that both involve math.pi introduces rounding error, so the ratio may be just below the exact integer and int() truncation produces the wrong result. Avoid the redundant floating-point division; compute the ratio purely with the integer radius (e.g. `answer = r * r`) before printing.

## Sample 3 — problem p00491

```python
N,K=map(int,input().split())
S=[0]*N
for _ in[0]*K:
 a,b=map(int,input().split())
 S[a-1]=b
dp=[0]*9
st,nd=S[:2]
if st:
 if nd:dp[~-st*3+~-nd]=1
 else:dp[~-st*3:st*3]=[1]*3
elif nd:dp[~-st::3]=[1]*3
else:dp=[1]*9
for i in range(2,N):
 cur=S[i]-1;tmp=[0]*9
 if cur>0:
  for k in range(3):tmp[k*3+cur]=sum(dp[k::3])-dp[cur*4]*(k==cur)
 else:
  for cur in range(3):
   for k in range(3):tmp[k*3+cur]=sum(dp[k::3])-dp[cur*4]*(k==cur)
 dp=tmp[:]
print(sum(dp)%10000)
```

> The bug is in lines 17-18 (`else:`). Lines 17-18 mistakenly reuse the loop variable name `cur` for both the spectral index and the new iteration, causing the outer `cur` value from S[i]-1 to be discarded and breaking the conditional logic that differentiates constrained vs. unconstrained digits. Rename the inner loop variable (e.g. to `digit`) so the original `cur` value remains intact when computing `tmp` for the unconstrained case.

## Sample 4 — problem p02270

```python

# ?????§?????????P???K??°?????????????????§???????????????????????????????
def check(P):
    i = 0
    for j in range(k):
        s = 0
        while s + w[i] <= P:
            s += w[i]
            i += 1
            if i == n:
                return n
    return i


def solve():
    left = 0
    right = max(w) + 1  # ??????????????°???* 1????????????????????§??????
    while right - left > 1:
        mid = (left + right) / 2
        v = check(mid)  # mid == P ??¨???????????§???????????????????????????
        if v >= n:
            right = mid
        else:
            left = mid

    return right

if __name__ == "__main__":
    n, k = map(int, input().split())
    w = [int(input()) for i in range(n)]
    print(int(solve()))
```

> The bug is in lines 19-22 (`mid = (left + right) / 2`). The binary search is mixing floats by dividing with /, so left and right become non-integer and the loop never converges on the intended integer capacity; that makes check(mid) operate on fractional P values and the final return is wrong. Change the midpoint calculation to integer division, e.g. use mid = (left + right) // 2, ensuring the binary search stays in the integer domain and converges correctly.

## Sample 5 — problem p03773

```python
a, b = map(int, input().split())

if a+b>24:
  print(a+b-24)
else:
  print(a+b)
```

> The bug is in lines 5-6 (`else:`). The failure occurs in the else branch because it simply prints a+b even when the sum reaches 0 mod 24, so the wraparound logic never executes for sums ≥24. Replace the else block with logic that mirrors the wraparound (e.g., print((a+b) % 24)) so that all non-wrapping sums are handled correctly.
