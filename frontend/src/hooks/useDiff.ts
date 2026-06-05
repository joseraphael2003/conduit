export interface DiffBlock {
  type: "equal" | "delete" | "insert" | "change";
  oldWords: string[];
  newWords: string[];
}

function longestCommonSubsequence<T>(a: T[], b: T[]): T[] {
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array(m + 1)
    .fill(0)
    .map(() => Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  const lcs: T[] = [];
  let i = m;
  let j = n;
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) {
      lcs.unshift(a[i - 1]);
      i--;
      j--;
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--;
    } else {
      j--;
    }
  }

  return lcs;
}

export function computeDiff(oldText: string, newText: string): DiffBlock[] {
  if (!oldText && !newText) return [];
  if (!oldText)
    return [{ type: "insert", oldWords: [], newWords: newText.split(/\s+/) }];
  if (!newText)
    return [{ type: "delete", oldWords: oldText.split(/\s+/), newWords: [] }];

  const oldWords = oldText.split(/(\s+)/).filter((w) => w.length > 0);
  const newWords = newText.split(/(\s+)/).filter((w) => w.length > 0);

  const lcs = longestCommonSubsequence(oldWords, newWords);

  const blocks: DiffBlock[] = [];
  let oldIdx = 0;
  let newIdx = 0;
  let lcsIdx = 0;

  while (oldIdx < oldWords.length || newIdx < newWords.length) {
    if (
      lcsIdx < lcs.length &&
      oldIdx < oldWords.length &&
      newIdx < newWords.length &&
      oldWords[oldIdx] === lcs[lcsIdx] &&
      newWords[newIdx] === lcs[lcsIdx]
    ) {
      const equalWords: string[] = [];
      while (
        lcsIdx < lcs.length &&
        oldIdx < oldWords.length &&
        newIdx < newWords.length &&
        oldWords[oldIdx] === lcs[lcsIdx] &&
        newWords[newIdx] === lcs[lcsIdx]
      ) {
        equalWords.push(lcs[lcsIdx]);
        oldIdx++;
        newIdx++;
        lcsIdx++;
      }
      blocks.push({ type: "equal", oldWords: equalWords, newWords: equalWords });
    } else {
      const oldRun: string[] = [];
      const newRun: string[] = [];

      while (
        oldIdx < oldWords.length &&
        !(lcsIdx < lcs.length && oldWords[oldIdx] === lcs[lcsIdx])
      ) {
        oldRun.push(oldWords[oldIdx]);
        oldIdx++;
      }

      while (
        newIdx < newWords.length &&
        !(lcsIdx < lcs.length && newWords[newIdx] === lcs[lcsIdx])
      ) {
        newRun.push(newWords[newIdx]);
        newIdx++;
      }

      if (oldRun.length > 0 && newRun.length > 0) {
        blocks.push({ type: "change", oldWords: oldRun, newWords: newRun });
      } else if (oldRun.length > 0) {
        blocks.push({ type: "delete", oldWords: oldRun, newWords: [] });
      } else if (newRun.length > 0) {
        blocks.push({ type: "insert", oldWords: [], newWords: newRun });
      }
    }
  }

  return blocks;
}

export function useDiff() {
  return { computeDiff };
}
