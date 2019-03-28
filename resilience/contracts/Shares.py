import logging

from ..actions import RedeemShares
from economicsl import Contract


# This contract represents a bunch of shares of some Institution which can issue shares.
class Shares(Contract):
    ctype = 'Shares'

    def __init__(self, owner, issuer, nShares, originalNAV):
        super().__init__(owner, issuer)
        self.nShares = nShares
        self.originalNumberOfShares = nShares
        self.previousValueOfShares = self.get_new_value()
        self.originalNAV = originalNAV
        self.nSharesPendingToRedeem = 0

        assert issuer is not None

    def get_name(self, me):
        if me == self.assetParty:
            return "Shares of the firm: " + self.liabilityParty.get_name()
        else:
            return "Shares owned by our shareholder " + self.assetParty.get_name()

    def redeem(self, number, amount):
        assert number <= self.nShares
        self.liabilityParty.get_ledger().subtract_cash(amount)
        # TODO this is disabled because AM investor is disabled for now
        # self.assetParty.get_ledger().sell_asset(number * nav, self)
        self.nShares -= number
        self.nSharesPendingToRedeem -= number

    def get_value(self):
        return self.previousValueOfShares

    def get_new_value(self):
        return self.nShares * self.liabilityParty.get_net_asset_value()

    def get_NAV(self):
        return self.liabilityParty.get_net_asset_value()

    def get_nShares(self):
        return self.nShares

    def get_action(self, me):
        return RedeemShares(me, self)

    def is_eligible(self, me):
        return (me == self.assetParty) and self.nShares > 0

    def update_value(self):
        valueChange = self.get_new_value() - self.previousValueOfShares
        self.previousValueOfShares = self.get_new_value()
        return

        # accounting disabled because AM Investor is disabled
        if valueChange > 0:
            self.assetParty.get_ledger().appreciate_asset(self, valueChange)
            self.liabilityParty.get_ledger().appreciate_liability(self, valueChange)
        elif valueChange < 0:
            logging.debug("value of shares fell.")
            self.assetParty.get_ledger().devalue_asset(self, -1.0 * valueChange)
            self.liabilityParty.get_ledger().devalue_liability(self, -1.0 * valueChange)

    def get_original_NAV(self):
        return self.originalNAV

    def add_shares_pending_to_redeem(self, number):
        self.nSharesPendingToRedeem += number

    def get_nShares_pending_to_redeem(self):
        return self.nSharesPendingToRedeem

    def get_original_number_of_shares(self):
        return self.originalNumberOfShares