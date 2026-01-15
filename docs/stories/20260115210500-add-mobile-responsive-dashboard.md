# Add Mobile Responsive Dashboard

## Summary

Added responsive CSS media queries to the dashboard to enable proper viewing on mobile phones and tablets. The layout now adapts to different screen sizes while keeping the price chart readable.

## Context / Problem

The dashboard was designed for desktop browsers and did not render properly on mobile devices:
- Header elements overlapped with tab navigation
- The 3-column expansion layout (Orders | Chart | Trades) was too cramped
- Text and buttons were too small for touch devices
- The price chart became unreadable on narrow screens

## What Changed

### Files Modified

- **`dashboard/assets/css/theme.css`** - Added responsive CSS media queries

### Breakpoints Implemented

1. **Tablet (< 900px)**
   - Chart moves to top of expansion, full width
   - Orders and Trades sections side by side below

2. **Mobile (< 600px)**
   - Header: Shows only Status + Total P&L + Timestamp
   - Tabs: Icons only (no labels)
   - Pair row: Symbol + Price + Order count (P&L hidden)
   - Expansion: Chart on top (full width), Orders/Trades below
   - Compact font sizes and padding

3. **Small phone (< 400px)**
   - Orders and Trades stack vertically
   - Smaller chart height (140px)
   - More compact UI elements

4. **Touch devices**
   - Larger touch targets (min 36px)
   - Hidden scrollbars

5. **Landscape phone**
   - Optimized for horizontal orientation
   - Reduced vertical spacing

### Layout on Mobile

```
+---------------------------+
| HEALTHY      +0.81  21:09 |  <- Simplified header
+---------------------------+
|  [D]   [H]   [C]          |  <- Icon-only tabs
+---------------------------+
| > SOL/USDT   $141.42    5 |  <- Compact pair row
+---------------------------+
| [1H][4H][1D][1W]          |
| +-------------------------+
| |    PRICE CHART          |  <- Chart first, full width
| |      (160px)            |
| +-------------------------+
| ORDERS    | RECENT TRADES |  <- Side by side below
| 5 BUY     | SELL $143     |
| 0 SELL    | BUY  $137     |
+---------------------------+
```

## How to Test

1. **Browser DevTools responsive mode:**
   ```
   - Open http://cryptotrader-dashboard.com
   - Press F12 to open DevTools
   - Click the device toggle icon (Ctrl+Shift+M)
   - Test at widths: 320px, 480px, 600px, 768px, 900px
   ```

2. **Test on actual mobile device:**
   - Navigate to http://cryptotrader-dashboard.com on phone
   - Verify header doesn't overlap tabs
   - Expand a pair and verify chart is readable
   - Test both portrait and landscape orientations

3. **Key elements to verify:**
   - Header shows: Status, Total P&L, Timestamp
   - Tabs show only icons on mobile
   - Pair rows show: Symbol, Price, Order count
   - Expanded view: Chart on top, Orders/Trades below
   - Chart is at least 300px wide (readable)
   - Touch targets are large enough (no misclicks)

## Risk / Rollback Notes

### Risks

- **CSS specificity conflicts**: The responsive styles use `!important` in some places which could conflict with future NiceGUI/Quasar updates
- **Untested browsers**: Tested primarily on Chrome; Safari and Firefox mobile may have minor differences

### Rollback

1. Remove the "Mobile Responsive Styles" section from `dashboard/assets/css/theme.css`
2. Rebuild and deploy: `gcloud builds submit --tag europe-west6-docker.pkg.dev/cryptotrader-bot-20260115/docker-repo-eu/cryptotrader:latest`
3. SSH to VM and restart container with new image
