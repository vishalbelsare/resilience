import logging

import numpy as np

from ..contracts import Shares
from ..parameters import eps, isequal_float
from .Institution import Institution
from .DefaultException import DefaultException


class AssetManager(Institution):
    def __init__(self, name, model):
        super().__init__(name, model)
        self.shares = []
        self.nShares = 0
        self.NAV_lr_previous = 0  # lr stands for loss relative
        self.nShares_extra_previous = 0

    def update_value_of_all_shares(self):
        for share in self.shares:
            share.update_value()

    def issue_shares(self, owner, quantity):
        self.nShares += quantity
        self.update_value_of_all_shares()
        return Shares(owner, self, quantity, self.get_net_asset_value())

    def get_net_asset_value(self):
        if self.nShares > 0:
            return self.get_equity_value() / self.nShares
        return 0

    def get_nShares(self):
        return self.nShares

    def step(self):
        super().step()

    def get_equity_loss(self):
        return 0.0

    def pay_matured_cash_commitments_or_default(self):
        maturedPullFunding = self.get_matured_obligations()
        if maturedPullFunding > 0:
            logging.debug("We have matured payment obligations for a total of %.2f" % maturedPullFunding)
            if (self.get_ue_cash() >= maturedPullFunding - eps):
                self.fulfil_matured_requests()
            else:
                logging.debug("A matured obligation was not fulfilled.\nDEFAULT DUE TO LACK OF LIQUIDITY")
                raise DefaultException(self, DefaultException.TypeOfDefault.LIQUIDITY)

    def trigger_default(self):
        super().trigger_default()
        # perform firesale assets
        self.sell_assets_proportionally()

    def choose_actions(self):
        NAV = self.get_net_asset_value()
        logging.debug("\nMy NAV is %f" % NAV)
        if NAV < 0:
            # Equity is negative, probably due to price fell
            raise DefaultException(self, DefaultException.TypeOfDefault.SOLVENCY)

        # 1) Redeem shares or default
        # self.pay_matured_cash_commitments_or_default()  # not used since AM investor is disabled

        assert self.nShares >= self.nShares_extra_previous, (self.nShares, self.nShares_extra_previous)  # sanity check so that the AM doesn't over-redeem
        _amount_to_redeem = self.nShares_extra_previous * self.NAV_previous
        if self.get_ue_cash() < _amount_to_redeem:
            raise DefaultException(self, DefaultException.TypeOfDefault.LIQUIDITY)
        share = self.shares[0]  # There is only 1 share object
        share.redeem(self.nShares_extra_previous, _amount_to_redeem)
        self.nShares -= self.nShares_extra_previous
        self.update_value_of_all_shares()

        # 2) Firesell to meet current NAV loss
        assert NAV <= self.NAV_previous + eps, (NAV, self.NAV_previous)
        _mul = 2.5
        if self.NAV_lr_previous > 0 and self.nShares > 0:
            assert isequal_float(self.nShares, (1 - _mul * self.NAV_lr_previous) * self.nShares_initial), (self.nShares, self.NAV_lr_previous, self.nShares_initial)
        # lr stands for loss relative
        NAV_lr = (self.NAV_initial - NAV) / self.NAV_initial
        if NAV_lr > self.NAV_lr_previous:
            # This ensures 0 <= nShares_extra <= self.nShares
            nShares_extra = np.clip(_mul * self.nShares_initial * (NAV_lr - self.NAV_lr_previous), 0, self.nShares)

            # Firesale to raise that liquidity
            self.sell_assets_proportionally(nShares_extra * NAV)
            self.nShares_extra_previous = nShares_extra

        else:
            self.nShares_extra_previous = 0

        # update f^{t-1}, NAV^{t-1}
        self.NAV_lr_previous = NAV_lr
        self.NAV_previous = NAV

        # 3) Firesell extra assets to get enough cash if it is too low
        _A = self.get_ledger().get_asset_value()
        _C = self.get_cash_()
        if _C / _A < 0.9 * self.cash_fraction_initial:
            self.sell_assets_proportionally(_A * self.cash_fraction_initial - _C)