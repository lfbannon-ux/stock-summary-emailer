# Fully Automated Daily Stock Summary Email Service

**Automated daily stock summaries with fresh research, delivered via email using Railway, GitHub, SendGrid, and Claude API.**

## 🎯 What This Does

Every day at your scheduled time, this service will:
1. ✅ **Call Claude API** to generate fresh stock summaries with web research
2. ✅ **Analyze 10 Australian stocks** with current prices, news, and industry trends
3. ✅ **Format as professional HTML email**
4. ✅ **Send automatically** to your specified recipients
5. ✅ **Tag new information** with [NEW] markers
6. ✅ **Include dated sources** for all industry trends

**Zero manual work required after setup!**

---

## 📊 Stocks Covered

1. Charter Hall Group (CHC.AX) - Property/Funds Management
2. Macquarie Group (MQG.AX) - Investment Banking
3. Hansen Technologies (HSN.AX) - Utility Billing Software
4. HUB24 (HUB.AX) - Wealth Platform
5. PEXA (PXA.AX) - Property Settlements
6. Sigma Healthcare (SIG.AX) - Pharmacy Wholesale
7. Mineral Resources (MIN.AX) - Lithium/Iron Ore
8. Supply Network (SNL.AX) - IT Distribution
9. Dicker Data (DDR.AX) - IT Distribution
10. CSL Limited (CSL.AX) - Biotech/Plasma

---

## 💰 Cost Breakdown

| Service | Cost | Details |
|---------|------|---------|
| **SendGrid** | $0/month | Free tier: 100 emails/day |
| **Railway** | $5/month or $0 | $5 credit free tier covers cron jobs |
| **Claude API** | ~$15-30/month | Estimated based on daily usage |
| **GitHub** | $0/month | Free for private repos |
| **TOTAL** | **~$15-30/month** | Mostly Claude API costs |

**Claude API Cost Breakdown:**
- Each daily summary: ~$0.50-1.00 (depending on research depth)
- 30 days/month: ~$15-30/month
- Uses Claude Sonnet 4 with web search for fresh data

---

## 🚀 Setup Instructions

### **STEP 1: Get API Keys**

#### 1a. Anthropic API Key
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Go to **API Keys** section
4. Click **Create Key**
5. Name it: "Daily Stock Summaries"
6. **Copy the API key** (starts with `sk-ant-...`)
7. Add credits to your account ($20-50 recommended to start)

#### 1b. SendGrid API Key
1. Go to https://sendgrid.com/
2. Sign up for free account
3. Go to **Settings** → **API Keys**
4. Click **Create API Key**
5. Choose **Full Access** or enable "Mail Send"
6. **Copy the API key**

#### 1c. Verify Sender Email
1. In SendGrid: **Settings** → **Sender Authentication**
2. Click **Verify a Single Sender**
3. Enter the email you'll send FROM
4. Verify via email link

---

### **STEP 2: Upload to GitHub**

```bash
cd stock_summary_emailer_v2
git init
git add .
git commit -m "Initial commit: Automated stock summary emailer"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/stock-summary-emailer.git
git push -u origin main
```

---

### **STEP 3: Deploy to Railway**

1. Go to https://railway.app/
2. Create **New Project** → **Deploy from GitHub repo**
3. Select your `stock-summary-emailer` repository
4. Railway will auto-detect Python and deploy

---

### **STEP 4: Configure Environment Variables**

In Railway project → **Variables** tab, add:

**Required Variables:**

```
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
SENDGRID_API_KEY=your-sendgrid-key-here
FROM_EMAIL=your-verified-email@example.com
RECIPIENT_EMAILS=email1@example.com,email2@example.com
```

**Variable Details:**
- `ANTHROPIC_API_KEY`: From console.anthropic.com
- `SENDGRID_API_KEY`: From sendgrid.com
- `FROM_EMAIL`: Must be verified in SendGrid
- `RECIPIENT_EMAILS`: Comma-separated, no spaces

---

### **STEP 5: Set Up Daily Cron Job**

In Railway:
1. Go to your service → **Settings**
2. Find **Cron** section
3. Add schedule:
   - **For 8 AM Sydney time:** `21 * * *` (9 PM UTC previous day)
   - **For 9 AM Sydney time:** `22 * * *` (10 PM UTC previous day)
   - **Weekdays only at 8 AM:** `21 * * 1-5`

4. Set command: `python main.py`

**Timezone Notes:**
- Railway uses UTC
- Sydney is UTC+11 (summer) or UTC+10 (winter)
- Adjust cron schedule accordingly

---

### **STEP 6: Test the System**

1. **Manual test in Railway:**
   - Click **Deploy** → **Trigger Deploy**
   - Watch logs (should take 1-2 minutes for Claude to generate content)
   - Look for: `✅ Email sent to [email]: Status 202`

2. **Check your email:**
   - Should receive professionally formatted HTML email
   - Check spam folder if not in inbox

3. **Monitor costs:**
   - Check Anthropic console for API usage
   - Should be ~$0.50-1.00 per daily run

---

## 🎨 Customizing the Prompt

The prompt that controls what Claude generates is in `main.py` in the `generate_stock_summary_with_claude()` function.

### **To Change What's Included:**

Edit the `prompt` variable in `main.py`:

```python
prompt = f"""Generate a comprehensive daily stock summary report for {today} for the following 10 Australian stocks:

1. Charter Hall Group (CHC.AX)
2. Macquarie Group (MQG.AX)
...

For EACH stock, provide:
[Your custom instructions here]
"""
```

### **Examples of Customizations:**

**Add dividend focus:**
```python
- Include any dividend announcements or changes
- Highlight yield changes if material
```

**Add sector summaries:**
```python
- At the end, provide a 1-paragraph summary for each sector:
  * Property (Charter Hall)
  * Banking/Finance (Macquarie, HUB24)
  * Resources (Mineral Resources)
  * Healthcare (CSL, Sigma)
```

**Change format:**
```python
- Use bullet points instead of paragraphs
- Limit each company to 3-4 sentences maximum
- Focus only on material price moves >2%
```

### **To Deploy Changes:**

After editing `main.py`:
```bash
git add main.py
git commit -m "Update prompt for [your change]"
git push
```

Railway will auto-deploy the changes.

---

## 📊 What the Email Looks Like

Each email includes:
- **Clean HTML formatting** with professional styling
- **Price & Move** for each stock (green for up, red for down)
- **Reason for Move** (fundamental catalysts only)
- **Company Developments** with [NEW] tags
- **Industry Dynamics** with dates and sources
- **Focus on fundamentals:** volumes, pricing, customers, competitive position

Example section:
```
CHARTER HALL GROUP (CHC.AX)
A$25.02 | -A$0.05 (-0.20%)

REASON FOR MOVE: No specific catalyst; minor pullback after recent gains.

COMPANY DEVELOPMENTS:
• [NEW] FY26 earnings guidance raised 5.5% to 95.0 cents per security...
• Earnings date: Feb 19, 2026

INDUSTRY/COMPETITIVE DYNAMICS:
• Dec 2025 - Property Market Recovery: All three core asset classes 
  delivered positive returns in Q3 2025... (KPMG Commercial Property Update)
```

---

## 🔧 Troubleshooting

### **Emails Not Sending**

1. **Check Railway logs:**
   - Look for error messages
   - Common issues: API key errors, email verification

2. **Verify environment variables:**
   - All 4 variables set correctly?
   - No extra spaces in emails?
   - FROM_EMAIL verified in SendGrid?

3. **Check SendGrid dashboard:**
   - Go to **Activity** to see delivery attempts
   - Check for bounces or rejections

### **Claude API Errors**

**Error: "Invalid API key"**
- Check ANTHROPIC_API_KEY is set correctly
- Verify key at console.anthropic.com

**Error: "Insufficient credits"**
- Add more credits to Anthropic account
- Check usage at console.anthropic.com

**Error: "Rate limit exceeded"**
- Shouldn't happen with daily runs
- Check if script is running multiple times

### **High Claude API Costs**

If costs are higher than expected:
1. Check Railway logs - is it running multiple times?
2. Verify cron schedule - should run once daily
3. Consider reducing the prompt length
4. Use Claude Haiku instead (cheaper but less capable)

### **Content Quality Issues**

If summaries aren't detailed enough:
- Edit the prompt in `main.py` to be more specific
- Add examples of what you want
- Increase `max_tokens` (currently 16000)

If summaries are too long:
- Ask for more concise output in prompt
- Limit to specific sections
- Focus on material changes only

---

## 📈 Monitoring & Maintenance

### **Daily Checks (Optional):**
- Review email for quality
- Check Railway logs for errors
- Monitor Anthropic API costs

### **Weekly:**
- Review Anthropic usage/costs
- Check SendGrid delivery rates
- Verify all 10 stocks still relevant

### **Monthly:**
- Adjust prompt if needed
- Review cost vs. value
- Update stock list if required

---

## 🔄 Future Enhancements

Possible additions:
- [ ] Add SMS alerts for significant moves (>5%)
- [ ] PDF attachment with detailed analysis
- [ ] Weekly summary email on Fridays
- [ ] Slack/Discord integration
- [ ] Database to track historical changes
- [ ] Alert if stock hits 52-week high/low
- [ ] Customized alerts per stock

---

## 💡 Tips for Best Results

1. **Prompt Engineering:** The better your prompt, the better the output
2. **Cost Management:** Start with basic prompt, add detail gradually
3. **Monitoring:** Check first week daily to ensure quality
4. **Timing:** Schedule for early morning before market opens
5. **Spam Filters:** Add sender to address book to avoid spam folder

---

## 🆘 Support Resources

- **Anthropic Docs:** https://docs.anthropic.com/
- **SendGrid Docs:** https://docs.sendgrid.com/
- **Railway Docs:** https://docs.railway.app/
- **Claude API Pricing:** https://www.anthropic.com/pricing

---

## 📝 License

MIT License - Use and modify as needed for personal use.

---

**Questions? Issues?**
- Check Railway logs first
- Review Anthropic console for API errors  
- Test SendGrid separately if emails fail
- Verify all environment variables are set correctly
