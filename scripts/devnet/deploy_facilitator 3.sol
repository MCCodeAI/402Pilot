// SPDX-License-Identifier: MIT
//
// 402Pilot — minimal x402 facilitator + USDC mock for the DevnetDemo
// reproducibility witness.
//
// SCOPE: This contract is illustrative. It mirrors the on-chain surface
// that 402Pilot's x402 wrapper relies on (atomic charge → emit event)
// without depending on an external x402 deployment. The benchmark replays
// do NOT use this contract; only the viz/Explainer/DevnetDemo does.
//
// solhint-disable-next-line compiler-version
pragma solidity ^0.8.20;

interface IERC20Min {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address) external view returns (uint256);
}

/// @title MockUSDC — ERC20-ish stand-in for USDC on a local fork
contract MockUSDC {
    string public constant name = "Mock USD Coin";
    string public constant symbol = "USDC";
    uint8  public constant decimals = 6;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    function mint(address to, uint256 amount) external {
        // Open mint; this is a devnet-only mock.
        balanceOf[to] += amount;
        emit Transfer(address(0), to, amount);
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        return _transfer(msg.sender, to, amount);
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        require(a >= amount, "USDC: allowance");
        if (a != type(uint256).max) {
            allowance[from][msg.sender] = a - amount;
        }
        return _transfer(from, to, amount);
    }

    function _transfer(address from, address to, uint256 amount) internal returns (bool) {
        require(balanceOf[from] >= amount, "USDC: balance");
        balanceOf[from] -= amount;
        balanceOf[to]   += amount;
        emit Transfer(from, to, amount);
        return true;
    }
}

/// @title X402Facilitator — minimal "pay-and-call" settlement contract.
///        Caller pre-approves USDC for `payer`; facilitator pulls the
///        amount and emits a Settlement event the agent's wrapper can
///        watch for.
contract X402Facilitator {
    IERC20Min public immutable token;
    address   public immutable receiver;

    event Settlement(
        address indexed payer,
        address indexed receiver,
        bytes32 indexed callId,
        uint256 amount,
        uint64  timestamp
    );

    constructor(address _token, address _receiver) {
        token    = IERC20Min(_token);
        receiver = _receiver;
    }

    /// @notice Settle one paid call. The agent pre-approves USDC, then
    ///         calls this function. The receiver is fixed at deploy time
    ///         to keep the surface minimal.
    function settle(
        address payer,
        uint256 amount,
        bytes32 callId
    ) external {
        require(amount > 0, "X402: zero");
        bool ok = token.transferFrom(payer, receiver, amount);
        require(ok, "X402: transferFrom");
        emit Settlement(payer, receiver, callId, amount, uint64(block.timestamp));
    }
}
